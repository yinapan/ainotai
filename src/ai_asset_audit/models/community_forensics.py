from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


def _build_custom_vit():
    """Build a ViT-Small/16 (384px) matching OwensLab/commfor-model-384 keys.

    Key naming: vit.cls_token, vit.pos_embed, vit.patch_embed.proj.*,
    vit.blocks.{i}.{attn.qkv,attn.proj,mlp.fc1,mlp.fc2,norm1,norm2}.*,
    vit.norm.*, vit.head.*
    """
    import torch
    import torch.nn as nn

    class PatchEmbed(nn.Module):
        def __init__(self, img_size=384, patch_size=16, in_chans=3, embed_dim=384):
            super().__init__()
            self.proj = nn.Conv2d(in_chans, embed_dim, kernel_size=patch_size, stride=patch_size)

        def forward(self, x):
            x = self.proj(x)  # [B, 384, 24, 24]
            x = x.flatten(2).transpose(1, 2)  # [B, 576, 384]
            return x

    class Attention(nn.Module):
        def __init__(self, dim=384, num_heads=6):
            super().__init__()
            self.num_heads = num_heads
            self.head_dim = dim // num_heads
            self.scale = self.head_dim ** -0.5
            self.qkv = nn.Linear(dim, dim * 3)
            self.proj = nn.Linear(dim, dim)

        def forward(self, x):
            B, N, C = x.shape
            qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim).permute(2, 0, 3, 1, 4)
            q, k, v = qkv[0], qkv[1], qkv[2]
            attn = (q @ k.transpose(-2, -1)) * self.scale
            attn = attn.softmax(dim=-1)
            x = (attn @ v).transpose(1, 2).reshape(B, N, C)
            return self.proj(x)

    class Mlp(nn.Module):
        def __init__(self, in_features=384, hidden_features=1536):
            super().__init__()
            self.fc1 = nn.Linear(in_features, hidden_features)
            self.fc2 = nn.Linear(hidden_features, in_features)
            self.act = nn.GELU()

        def forward(self, x):
            return self.fc2(self.act(self.fc1(x)))

    class Block(nn.Module):
        def __init__(self, dim=384, num_heads=6):
            super().__init__()
            self.norm1 = nn.LayerNorm(dim, eps=1e-6)
            self.attn = Attention(dim, num_heads)
            self.norm2 = nn.LayerNorm(dim, eps=1e-6)
            self.mlp = Mlp(dim, dim * 4)

        def forward(self, x):
            x = x + self.attn(self.norm1(x))
            x = x + self.mlp(self.norm2(x))
            return x

    class CustomViT(nn.Module):
        def __init__(self):
            super().__init__()
            self.patch_embed = PatchEmbed()
            self.cls_token = nn.Parameter(torch.zeros(1, 1, 384))
            num_patches = (384 // 16) ** 2  # 576
            self.pos_embed = nn.Parameter(torch.zeros(1, num_patches + 1, 384))
            self.blocks = nn.ModuleList([Block() for _ in range(12)])
            self.norm = nn.LayerNorm(384, eps=1e-6)
            self.head = nn.Linear(384, 1)

        def forward(self, x):
            B = x.shape[0]
            x = self.patch_embed(x)
            cls_tokens = self.cls_token.expand(B, -1, -1)
            x = torch.cat((cls_tokens, x), dim=1)
            x = x + self.pos_embed
            for blk in self.blocks:
                x = blk(x)
            x = self.norm(x)
            return self.head(x[:, 0])

    return CustomViT()


class CommunityForensicsDetector(BaseDetector):
    """Community-Forensics AI-generated image detector.

    Model: OwensLab/commfor-model-384 — ViT-Small/16 @ 384x384.
    Uses a custom ViT architecture to match the checkpoint key naming
    (no HuggingFace/transformers dependency needed for inference).

    Input: 384x384 RGB, output: AI probability via sigmoid.
    """

    name = "community_forensics"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.35):
        super().__init__(model_path, device, weight)

    def load(self) -> bool:
        try:
            import torch

            weight_file = None
            for pattern in ("*.safetensors", "*.pth", "*.pt", "*.bin"):
                for candidate in self.model_path.glob(pattern):
                    if "optimizer" in candidate.name or "training" in candidate.name:
                        continue
                    weight_file = candidate
                    break
                if weight_file:
                    break

            if not weight_file or not weight_file.exists():
                logger.error("Community-Forensics weights not found in %s", self.model_path)
                return False

            if weight_file.suffix == ".safetensors":
                from safetensors.torch import load_file
                state_dict = load_file(str(weight_file))
            else:
                state_dict = torch.load(weight_file, map_location=self.device, weights_only=True)

            # Strip "vit." prefix from checkpoint keys to match our CustomViT
            state_dict = {
                k.removeprefix("vit."): v for k, v in state_dict.items()
            }

            self._model = _build_custom_vit()
            self._model.load_state_dict(state_dict, strict=True)
            self._model.to(self.device)
            self._model.eval()

            logger.info("Loaded Community-Forensics (ViT-S/16) from %s", weight_file)
            return True

        except ImportError as e:
            logger.error("Missing dependency for Community-Forensics: %s", e)
            return False
        except Exception as exc:
            logger.error("Failed to load Community-Forensics: %s", exc)
            return False

    def predict(self, image: Image.Image) -> float:
        import torch
        import torchvision.transforms as T

        transform = T.Compose([
            T.Resize((384, 384)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        if image.mode != "RGB":
            image = image.convert("RGB")

        tensor = transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self._model(tensor)
            prob = torch.sigmoid(logits).item()

        return float(prob)
