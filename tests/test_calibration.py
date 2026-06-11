import threading
import time
from dataclasses import dataclass

from src.ai_asset_audit.pipeline import calibration


@dataclass
class DummyResult:
    confidence: float


def test_run_calibration_processes_categories_in_parallel(tmp_path, monkeypatch):
    for category in ("human", "ai_generated"):
        category_dir = tmp_path / category
        category_dir.mkdir()
        (category_dir / "sample.png").write_bytes(b"not-empty")

    calls = []
    lock = threading.Lock()

    def fake_run_pipeline(input_path, config):
        with lock:
            calls.append((input_path, threading.current_thread().name, time.perf_counter()))
        time.sleep(0.2)
        if input_path.endswith("human"):
            return [DummyResult(0.1)]
        return [DummyResult(0.9)]

    monkeypatch.setattr(calibration, "run_pipeline", fake_run_pipeline)

    started = time.perf_counter()
    result = calibration.run_calibration(
        tmp_path,
        {"thresholds": {"suspicious": 0.45}, "calibration": {"parallel_workers": 2}},
    )
    elapsed = time.perf_counter() - started

    assert result.total_samples == 2
    assert result.confusion == {"tp": 1, "fp": 0, "tn": 1, "fn": 0}
    assert elapsed < 0.35
    assert len({thread_name for _, thread_name, _ in calls}) == 2
