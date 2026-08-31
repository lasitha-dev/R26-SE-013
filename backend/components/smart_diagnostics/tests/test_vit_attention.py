"""
Unit tests for ViT Attention Rollout extraction (vit_attention.py).
==================================================================
Tests attention rollout computation, thresholding, connected components,
and module forward hook restoration.
"""

import numpy as np
import pytest
import torch
import torch.nn as nn
from PIL import Image

from components.smart_diagnostics.implementations.vit_attention import (
    compute_attention_rollout,
    extract_attention_rollout,
)


class MockSelfAttention(nn.Module):
    def __init__(self, num_tokens=197):
        super().__init__()
        self.num_tokens = num_tokens

    def forward(self, query, key, value, need_weights=True, average_attn_weights=True):
        # Return synthetic attention weights with focal attention on specific tokens
        b = query.size(0)
        attn = torch.ones(b, self.num_tokens, self.num_tokens) / self.num_tokens
        # Put high attention on patch tokens 10..20
        attn[:, :, 10:20] += 0.5
        attn = attn / attn.sum(dim=-1, keepdim=True)
        out = query
        return out, attn


class MockEncoderBlock(nn.Module):
    def __init__(self, num_tokens=197):
        super().__init__()
        self.ln_1 = nn.Identity()
        self.self_attention = MockSelfAttention(num_tokens)
        self.dropout = nn.Identity()
        self.ln_2 = nn.Identity()
        self.mlp = nn.Identity()

    def forward(self, x):
        attn_out, _ = self.self_attention(x, x, x, need_weights=False)
        return x + attn_out


class MockViTModel(nn.Module):
    def __init__(self, num_layers=12, num_tokens=197):
        super().__init__()
        self.blocks = nn.ModuleList([MockEncoderBlock(num_tokens) for _ in range(num_layers)])
        self.heads = nn.Linear(768, 4)

    def forward(self, x):
        # x is (1, 3, 224, 224) -> mock token sequence (1, 197, 768)
        tokens = torch.randn(x.size(0), 197, 768, device=x.device)
        for block in self.blocks:
            tokens = block(tokens)
        cls_token = tokens[:, 0]
        return self.heads(cls_token)


class TestViTAttentionRollout:
    """Test suite for attention rollout algorithm and metric extraction."""

    def test_compute_attention_rollout_dimensions(self):
        """Rollout of 12 (1, 197, 197) attention tensors returns a (14, 14) map."""
        attns = [torch.softmax(torch.randn(1, 197, 197), dim=-1) for _ in range(12)]
        saliency_map = compute_attention_rollout(attns)

        assert isinstance(saliency_map, np.ndarray)
        assert saliency_map.shape == (14, 14)
        assert saliency_map.min() >= 0.0
        assert saliency_map.max() <= 1.0 + 1e-6

    def test_extract_attention_rollout_end_to_end(self):
        """Extract attention rollout from mock ViT model and verify returned metrics."""
        model = MockViTModel(num_layers=12)
        model.eval()
        dummy_tensor = torch.randn(1, 3, 224, 224)
        dummy_img = Image.new("RGB", (224, 224), color=(100, 150, 200))

        result = extract_attention_rollout(
            model,
            dummy_tensor,
            image_size=(224, 224),
            percentile_threshold=75.0,
            original_image=dummy_img,
        )

        assert "attention_map" in result
        assert "attention_coverage_pct" in result
        assert "attention_cluster_count" in result
        assert "attention_overlay_image" in result

        assert result["attention_map"].shape == (224, 224)
        assert 0.0 <= result["attention_coverage_pct"] <= 100.0
        assert result["attention_cluster_count"] >= 0
        assert isinstance(result["attention_overlay_image"], Image.Image)

    def test_extract_attention_rollout_restores_forwards(self):
        """Ensure original forward methods are cleanly restored after rollout extraction."""
        model = MockViTModel(num_layers=3)
        orig_forward = model.blocks[0].forward

        dummy_tensor = torch.randn(1, 3, 224, 224)
        _ = extract_attention_rollout(model, dummy_tensor, image_size=(224, 224))

        # Check forward method was restored
        assert model.blocks[0].forward == orig_forward
