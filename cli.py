from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

from src.ai_asset_audit.pipeline.offline_guard import check_offline_status
from src.ai_asset_audit.pipeline.pipeline import run_pipeline
from src.ai_asset_audit.pipeline.scorer import label_from_score
from src.ai_asset_audit.report.json_report import write_json_report
from src.ai_asset_audit.report.csv_report import write_csv_report
from src.ai_asset_audit.report.markdown_report import write_markdown_report
from src.ai_asset_audit.report.html_report import write_html_report
from src.ai_asset_audit.audit.code_audit import audit_code
from src.ai_asset_audit.audit.dependency_audit import audit_dependencies
from src.ai_asset_audit.metadata.signatures import load_signatures

logger = logging.getLogger("asset-audit")


def _load_config(path: str) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def cmd_doctor(args: argparse.Namespace) -> int:
    status = check_offline_status(probe_network=args.probe_network)
    tools = {
        name: shutil.which(name)
        for name in ("git", "docker", "exiftool", "c2patool", "aicheck", "blender", "python")
    }

    print("=== 离线环境检查 ===")
    print(f"  环境变量正常: {status.env_ok}")
    if status.missing_env:
        print(f"  缺失环境变量: {', '.join(status.missing_env)}")
    print(f"  网络已阻断: {status.network_blocked}")
    print()
    print("=== 工具状态 ===")
    for name, path in tools.items():
        mark = "OK" if path else "NOT FOUND"
        print(f"  {name}: {mark} ({path or '-'})")

    config = _load_config(args.config)
    models_config = config.get("models", {})
    print()
    print("=== 模型状态 ===")
    from src.ai_asset_audit.models import MODEL_REGISTRY
    for model_name in MODEL_REGISTRY:
        mc = models_config.get(model_name, {})
        enabled = mc.get("enabled", False) if isinstance(mc, dict) else False
        model_path = Path(mc.get("path", "")) if isinstance(mc, dict) else Path("")
        exists = model_path.exists() and any(model_path.iterdir()) if model_path.is_dir() else False
        status_text = "READY" if enabled and exists else "DISABLED" if not enabled else "MISSING"
        print(f"  {model_name}: {status_text} (path: {model_path})")

    if args.offline and not status.ok:
        print()
        print("ERROR: 离线模式检查失败", file=sys.stderr)
        return 4
    print()
    print("Doctor 检查完成。")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    if args.offline:
        status = check_offline_status(probe_network=args.probe_network)
        if not status.ok:
            print("ERROR: 离线模式违规。请设置离线环境变量并阻断网络。", file=sys.stderr)
            return 4

    config = _load_config(args.config)

    if args.layer == "metadata":
        config["forensics"] = {"enabled": False}
        config["models"] = {"enabled": False}
    elif args.layer == "forensics":
        config["models"] = {"enabled": False}

    thresholds = config.get("thresholds", {})
    results = run_pipeline(args.input, config)
    output_dir = args.output or config.get("report", {}).get("output_dir", "./reports")

    formats = config.get("report", {}).get("formats", ["json", "csv", "markdown"])
    if "json" in formats:
        write_json_report(results, output_dir)
    if "csv" in formats:
        write_csv_report(results, output_dir)
    if "markdown" in formats:
        write_markdown_report(results, output_dir)
    if "html" in formats:
        write_html_report(results, output_dir, args.input)

    print(f"扫描完成: {len(results)} 个文件。报告已写入 {Path(output_dir).resolve()}")

    high_risk = [r for r in results if r.final_label in {"Confirmed AI", "Likely AI"}]
    suspicious = [r for r in results if r.final_label == "Suspicious"]
    if high_risk:
        print(f"  高风险: {len(high_risk)} 个文件")
    if suspicious:
        print(f"  可疑: {len(suspicious)} 个文件")

    if high_risk and args.ci:
        return 2
    if suspicious and args.ci:
        return 1
    return 0


def cmd_audit_code(args: argparse.Namespace) -> int:
    findings = audit_code(args.path)
    payload = [
        {"path": f.path, "line": f.line, "category": f.category, "pattern": f.pattern, "text": f.text}
        for f in findings
    ]
    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"代码审计完成: {len(findings)} 条发现。结果已写入 {args.output}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if findings and args.ci else 0


def cmd_model_status(args: argparse.Namespace) -> int:
    from src.ai_asset_audit.models import MODEL_REGISTRY, MODEL_DESCRIPTIONS
    config = _load_config(args.config)
    models_config = config.get("models", {})
    print("=== 模型状态 ===")
    for model_name in MODEL_REGISTRY:
        mc = models_config.get(model_name, {})
        enabled = mc.get("enabled", False) if isinstance(mc, dict) else False
        model_path = Path(mc.get("path", "")) if isinstance(mc, dict) else Path("")
        weight = mc.get("weight", 0) if isinstance(mc, dict) else 0
        exists = model_path.exists() and any(model_path.iterdir()) if model_path.is_dir() else False
        status_text = "READY" if enabled and exists else "DISABLED" if not enabled else "MISSING"
        desc = MODEL_DESCRIPTIONS.get(model_name, "")
        print(f"  {model_name}: {status_text} (weight={weight}, path={model_path})")
        if desc:
            print(f"    {desc}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from src.ai_asset_audit.pipeline.calibration import run_calibration
    config = _load_config(args.config)
    if args.workers is not None:
        config.setdefault("calibration", {})["parallel_workers"] = args.workers
    result = run_calibration(args.benchmark, config)
    report = {
        "total_samples": result.total_samples,
        "per_category": result.per_category,
        "current_thresholds": result.current_thresholds,
        "recommended_thresholds": result.recommended_thresholds,
        "confusion_matrix": result.confusion,
    }
    output = Path(args.output)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"校准完成: {result.total_samples} 个样本")
    print(f"报告已写入 {output.resolve()}")
    if result.recommended_thresholds:
        print(f"推荐阈值: {result.recommended_thresholds}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asset-audit",
        description="保密美术资源 AI 离线审计与检测流水线",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="环境检查")
    doctor.add_argument("--offline", action="store_true", help="要求离线模式通过")
    doctor.add_argument("--probe-network", action="store_true", help="实际探测网络连通性")
    doctor.add_argument("--config", default="./config/config.yaml")
    doctor.set_defaults(func=cmd_doctor)

    scan = subparsers.add_parser("scan", help="扫描资源目录")
    scan.add_argument("input", help="输入资源目录或文件列表")
    scan.add_argument("--config", default="./config/config.yaml")
    scan.add_argument("--output", help="报告输出目录")
    scan.add_argument("--offline", action="store_true", help="强制离线模式")
    scan.add_argument("--probe-network", action="store_true")
    scan.add_argument("--ci", action="store_true", help="CI 模式，有风险时返回非零退出码")
    scan.add_argument("--layer", choices=["metadata", "forensics", "full"], default="full", help="检测层级")
    scan.add_argument("--mode", choices=["directory", "file-list", "git-diff"], default="directory")
    scan.add_argument("--base", help="git-diff 模式的基准分支")
    scan.set_defaults(func=cmd_scan)

    audit = subparsers.add_parser("audit-code", help="代码审计")
    audit.add_argument("path", help="待审计的代码目录")
    audit.add_argument("--output", help="结果输出文件路径")
    audit.add_argument("--ci", action="store_true")
    audit.add_argument("--offline", action="store_true")
    audit.set_defaults(func=cmd_audit_code)

    model = subparsers.add_parser("model", help="模型管理")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    model_status = model_sub.add_parser("status", help="查看模型状态")
    model_status.add_argument("--config", default="./config/config.yaml")
    model_status.add_argument("--offline", action="store_true")
    model_status.set_defaults(func=cmd_model_status)

    calibrate = subparsers.add_parser("calibrate", help="标注集校准阈值")
    calibrate.add_argument("benchmark", help="标注集目录 (子目录: human/ai_generated/ai_assisted/false_positive)")
    calibrate.add_argument("--config", default="./config/config.yaml")
    calibrate.add_argument("--output", default="./calibration_report.json")
    calibrate.add_argument("--workers", type=int, help="并行处理的类别目录数")
    calibrate.set_defaults(func=cmd_calibrate)

    return parser


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
