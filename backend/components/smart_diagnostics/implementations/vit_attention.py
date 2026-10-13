"""
ViT Attention Rollout Extraction Module
=======================================
Extracts attention rollout across all 12 transformer encoder layers of ViT-B/16
to produce a 14x14 saliency grid, coverage percentage, cluster count, and overlay.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models

try:
    from scipy.ndimage import label
except ImportError:
    label = None

logger = logging.getLogger("smart_diagnostics.vit_attention")


def compute_attention_rollout(
    attentions: list[torch.Tensor],
    discard_ratio: float = 0.0,
    head_fusion: str = "mean",
) -> np.ndarray:
    """Compute attention rollout from a list of attention weight tensors.

    Parameters
    ----------
    attentions : list[torch.Tensor]
        List of 12 tensors, each of shape (B, N, N) or (B, H, N, N).
    discard_ratio : float
        Fraction of smallest attention weights to prune per layer (default 0.0).
    head_fusion : str
        Method to aggregate multi-head attention ('mean', 'max', 'min').

    Returns
    -------
    np.ndarray
        Saliency map of shape (14, 14) normalized to [0, 1].
    """
    result = torch.eye(attentions[0].size(-1), device=attentions[0].device)

    with torch.no_grad():
        for attn in attentions:
            # Handle multihead attention tensor if heads dimension is present
            if attn.dim() == 4:
                if head_fusion == "mean":
                    attn_fused = attn.mean(dim=1)
                elif head_fusion == "max":
                    attn_fused = attn.max(dim=1)[0]
                elif head_fusion == "min":
                    attn_fused = attn.min(dim=1)[0]
                else:
                    attn_fused = attn.mean(dim=1)
            else:
                attn_fused = attn

            # Batch dimension (take item 0)
            if attn_fused.dim() == 3:
                attn_fused = attn_fused[0]

            # Discard lowest attention values if requested
            if discard_ratio > 0.0:
                flat = attn_fused.view(-1)
                k = int(flat.size(0) * discard_ratio)
                if k > 0:
                    val, _ = torch.kthvalue(flat, k)
                    attn_fused = torch.where(attn_fused < val, torch.zeros_like(attn_fused), attn_fused)

            # Add identity matrix to account for residual connections
            I = torch.eye(attn_fused.size(-1), device=attn_fused.device)
            a = (attn_fused + I) / 2.0
            a = a / (a.sum(dim=-1, keepdim=True) + 1e-12)

            result = torch.matmul(a, result)

    # Take the CLS token row (index 0), ignoring CLS-to-CLS (index 0)
    cls_attn = result[0, 1:]  # Shape: (196,) for ViT-B/16 (14x14 patches)
    num_patches = cls_attn.size(0)
    grid_size = int(np.sqrt(num_patches))

    if grid_size * grid_size != num_patches:
        grid_size = 14  # Default fallback

    saliency_map = cls_attn.view(grid_size, grid_size).cpu().numpy()

    # Min-Max normalize
    map_min, map_max = saliency_map.min(), saliency_map.max()
    if map_max - map_min > 1e-8:
        saliency_map = (saliency_map - map_min) / (map_max - map_min)
    else:
        saliency_map = np.zeros_like(saliency_map)

    return saliency_map


def extract_attention_rollout(
    model: nn.Module,
    input_tensor: torch.Tensor,
    image_size: Tuple[int, int] = (224, 224),
    percentile_threshold: float = 75.0,
    original_image: Optional[Image.Image] = None,
) -> Dict[str, Any]:
    """Execute forward pass capturing attention weights and compute rollout metrics.

    Parameters
    ----------
    model : nn.Module
        Loaded ViT model (eval mode).
    input_tensor : torch.Tensor
        Preprocessed image tensor (1, 3, H, W).
    image_size : Tuple[int, int]
        Target dimensions for upsampled saliency map.
    percentile_threshold : float
        Percentile threshold for binary attention mask (default 75.0 = top 25%).
    original_image : Optional[PIL.Image.Image]
        Base image to construct color overlay if provided.

    Returns
    -------
    dict
        - attention_map: np.ndarray (H, W) float in [0, 1]
        - raw_14x14_map: np.ndarray (14, 14) float in [0, 1]
        - attention_coverage_pct: float in [0, 100]
        - attention_cluster_count: int
        - attention_overlay_image: Optional[Image.Image]
    """
    attentions = []
    saved_forwards = {}

    # Inspect encoder blocks and temporarily wrap forward to request weights
    encoder_blocks = []
    for name, module in model.named_modules():
        # Match torchvision's EncoderBlock or custom blocks containing self_attention
        if hasattr(module, "self_attention") and hasattr(module, "ln_1"):
            encoder_blocks.append(module)

    def make_attn_hook(block):
        def forward_with_weights(x_in):
            x_ln = block.ln_1(x_in)
            attn_out, attn_weights = block.self_attention(
                x_ln, x_ln, x_ln, need_weights=True, average_attn_weights=True
            )
            attentions.append(attn_weights.detach())
            x_drop = block.dropout(attn_out)
            x_res = x_drop + x_in
            y = block.mlp(block.ln_2(x_res))
            return x_res + y
        return forward_with_weights

    # Temporarily substitute forward functions
    for block in encoder_blocks:
        saved_forwards[block] = block.forward
        block.forward = make_attn_hook(block)

    try:
        with torch.no_grad():
            _ = model(input_tensor)
    finally:
        # Guarantee restoration of original forward methods
        for block, orig_forward in saved_forwards.items():
            block.forward = orig_forward

    if not attentions:
        logger.warning("No attention weights captured from ViT model.")
        return {
            "attention_map": np.zeros(image_size, dtype=np.float32),
            "raw_14x14_map": np.zeros((14, 14), dtype=np.float32),
            "attention_coverage_pct": 0.0,
            "attention_cluster_count": 0,
            "attention_overlay_image": original_image,
        }

    # 1. Compute 14x14 rollout map
    raw_map = compute_attention_rollout(attentions)

    # 2. Upsample to target image size via PIL or Bilinear interpolation
    raw_pil = Image.fromarray((raw_map * 255).astype(np.uint8))
    upsampled_pil = raw_pil.resize(image_size, resample=Image.BILINEAR)
    upsampled_map = np.array(upsampled_pil, dtype=np.float32) / 255.0

    # 3. Thresholding for coverage and clusters
    thresh = float(np.percentile(upsampled_map, percentile_threshold))
    binary_mask = upsampled_map >= thresh

    # If saliency is flat or zero, handle edge case
    if thresh <= 1e-4:
        binary_mask = np.zeros_like(upsampled_map, dtype=bool)
        attention_coverage_pct = 0.0
    else:
        attention_coverage_pct = round(
            float(np.sum(binary_mask) / max(binary_mask.size, 1)) * 100.0, 2
        )

    # 4. Connected components
    cluster_count = 0
    if np.any(binary_mask):
        if label is not None:
            _, num_features = label(binary_mask)
            cluster_count = int(num_features)
        else:
            cluster_count = 1

    # 5. Optional Heatmap overlay
    overlay_image = None
    if original_image is not None:
        try:
            orig_rgb = original_image.resize(image_size).convert("RGB")
            # Build heat overlay: red channel proportional to attention
            heat_array = np.zeros((image_size[1], image_size[0], 4), dtype=np.uint8)
            heat_intensity = (upsampled_map * 255).astype(np.uint8)
            heat_array[..., 0] = heat_intensity  # Red
            heat_array[..., 1] = (heat_intensity * 0.2).astype(np.uint8)
            heat_array[..., 2] = 0
            heat_array[..., 3] = (heat_intensity * 0.5).astype(np.uint8)  # Alpha up to 50%

            heat_pil = Image.fromarray(heat_array, mode="RGBA")
            overlay_image = Image.alpha_composite(orig_rgb.convert("RGBA"), heat_pil).convert("RGB")
        except Exception as e:
            logger.debug("Could not generate attention overlay image: %s", e)
            overlay_image = original_image

    return {
        "attention_map": upsampled_map,
        "raw_14x14_map": raw_map,
        "attention_coverage_pct": attention_coverage_pct,
        "attention_cluster_count": cluster_count,
        "attention_overlay_image": overlay_image,
    }
