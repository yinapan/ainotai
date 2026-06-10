from .base import BaseDetector, DetectionResult
from .ensemble import EnsembleDetector, EnsembleResult

from .community_forensics import CommunityForensicsDetector
from .cnn_detection import CNNDetectionDetector
from .freq_detector import FreqDetector
from .clip_detector import ClipDetector
from .npr_detect import NprDetector
from .universal_fake import UniversalFakeDetector
from .sdxl_detector import SdxlDetector
from .dire_detector import DireDetector


MODEL_REGISTRY: dict[str, type[BaseDetector]] = {
    "community_forensics": CommunityForensicsDetector,
    "cnn_detection": CNNDetectionDetector,
    "freq_detect": FreqDetector,
    "clip_detector": ClipDetector,
    "npr": NprDetector,
    "universal_fake_detect": UniversalFakeDetector,
    "dire": DireDetector,
    "sdxl_detector": SdxlDetector,
}

MODEL_DESCRIPTIONS: dict[str, str] = {
    "community_forensics": "通用 AI 图片检测主力 (384x384, ResNet-50 backbone)",
    "cnn_detection": "CNNdetection 基线 (224x224, ResNet-50, ProGAN/StyleGAN 训练)",
    "freq_detect": "频域 DCT + RGB 双通道检测 (224x224, ResNet-34 backbone)",
    "clip_detector": "CLIP ViT-B/32 零样本检测 (224x224, 文本对比)",
    "npr": "AI 绘图风格检测 (256x256, NPR 专用)",
    "universal_fake_detect": "通用伪造检测 (224x224, UniversalFakeDetect)",
    "sdxl_detector": "SD/SDXL 专属检测 (transformers, Organika/sdxl-detector)",
}


def available_models() -> list[str]:
    return list(MODEL_REGISTRY)


def describe_models() -> dict[str, str]:
    return dict(MODEL_DESCRIPTIONS)


__all__ = [
    "BaseDetector",
    "DetectionResult",
    "EnsembleDetector",
    "EnsembleResult",
    "CommunityForensicsDetector",
    "CNNDetectionDetector",
    "FreqDetector",
    "ClipDetector",
    "NprDetector",
    "UniversalFakeDetector",
    "DireDetector",
    "SdxlDetector",
    "MODEL_REGISTRY",
    "MODEL_DESCRIPTIONS",
    "available_models",
    "describe_models",
]
