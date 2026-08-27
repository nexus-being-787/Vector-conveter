"""
VectorForge — Image Preprocessing Module
Stage 1: Input validation, EXIF correction, resize, denoise, alpha handling.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps, ExifTags

logger = logging.getLogger(__name__)

# Maximum longest edge after resize
MAX_DIMENSION = 2048
MIN_DIMENSION = 16


@dataclass
class PreparedImage:
    """Container for preprocessed image data."""
    array: np.ndarray          # HxWxC, uint8, BGR (OpenCV convention)
    has_alpha: bool
    alpha_channel: Optional[np.ndarray]  # HxW, uint8
    original_size: Tuple[int, int]       # (W, H)
    processed_size: Tuple[int, int]      # (W, H)
    was_resized: bool
    color_mode: str                      # "RGB", "RGBA", "L", "LA"


class ImagePreprocessor:
    """Handles all image preprocessing before the vectorization pipeline."""

    def __init__(
        self,
        max_dimension: int = MAX_DIMENSION,
        denoise: bool = True,
        denoise_strength: float = 3.0,
    ) -> None:
        self.max_dimension = max_dimension
        self.denoise = denoise
        self.denoise_strength = denoise_strength

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def prepare(self, source: str | Path | bytes) -> PreparedImage:
        """
        Full preprocessing pipeline.

        Args:
            source: File path, Path object, or raw bytes of the image.

        Returns:
            PreparedImage with corrected, resized, denoised image data.

        Raises:
            ValueError: If the image cannot be decoded or is too small.
        """
        pil_image = self._load(source)
        pil_image = self._fix_exif_orientation(pil_image)

        original_size = pil_image.size  # (W, H)
        color_mode = pil_image.mode
        has_alpha = color_mode in ("RGBA", "LA", "PA")

        # Separate alpha before any numeric processing
        alpha_channel: Optional[np.ndarray] = None
        if has_alpha:
            alpha_channel = self._extract_alpha(pil_image)

        # Convert to RGB for CV processing
        rgb_image = pil_image.convert("RGB")
        array = np.array(rgb_image, dtype=np.uint8)  # H x W x 3, RGB

        # Resize
        was_resized = False
        if max(array.shape[:2]) > self.max_dimension:
            array = self._resize(array)
            if alpha_channel is not None:
                alpha_channel = self._resize_alpha(alpha_channel, array.shape[:2])
            was_resized = True

        processed_size = (array.shape[1], array.shape[0])  # (W, H)

        self._validate_dimensions(processed_size)

        # Denoise
        if self.denoise:
            array = self._denoise(array)

        # Convert to BGR for OpenCV compatibility downstream
        bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)

        return PreparedImage(
            array=bgr,
            has_alpha=has_alpha,
            alpha_channel=alpha_channel,
            original_size=original_size,
            processed_size=processed_size,
            was_resized=was_resized,
            color_mode=color_mode,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load(source: str | Path | bytes) -> Image.Image:
        try:
            if isinstance(source, (str, Path)):
                img = Image.open(source)
            else:
                img = Image.open(io.BytesIO(source))
            img.verify()  # Check integrity
            # Re-open because verify() closes the file
            if isinstance(source, (str, Path)):
                img = Image.open(source)
            else:
                img = Image.open(io.BytesIO(source))
            return img
        except Exception as exc:
            raise ValueError(f"Cannot load image: {exc}") from exc

    @staticmethod
    def _fix_exif_orientation(img: Image.Image) -> Image.Image:
        """Auto-rotate image based on EXIF orientation tag."""
        try:
            return ImageOps.exif_transpose(img)
        except Exception:
            return img

    @staticmethod
    def _extract_alpha(pil_image: Image.Image) -> np.ndarray:
        """Extract alpha channel as uint8 numpy array."""
        if pil_image.mode == "RGBA":
            return np.array(pil_image.split()[3], dtype=np.uint8)
        if pil_image.mode in ("LA", "PA"):
            return np.array(pil_image.convert("LA").split()[1], dtype=np.uint8)
        return np.full(
            (pil_image.height, pil_image.width), 255, dtype=np.uint8
        )

    def _resize(self, array: np.ndarray) -> np.ndarray:
        """Resize so longest edge == max_dimension, preserve aspect ratio."""
        h, w = array.shape[:2]
        scale = self.max_dimension / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(array, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def _resize_alpha(
        self, alpha: np.ndarray, target_hw: Tuple[int, int]
    ) -> np.ndarray:
        h, w = target_hw
        return cv2.resize(alpha, (w, h), interpolation=cv2.INTER_AREA)

    def _denoise(self, array: np.ndarray) -> np.ndarray:
        """Apply mild Gaussian blur for noise reduction."""
        sigma = self.denoise_strength
        # Use kernel size derived from sigma (must be odd)
        k = int(2 * round(3 * sigma) + 1)
        if k < 3:
            k = 3
        return cv2.GaussianBlur(array, (k, k), sigma)

    @staticmethod
    def _validate_dimensions(size: Tuple[int, int]) -> None:
        w, h = size
        if w < MIN_DIMENSION or h < MIN_DIMENSION:
            raise ValueError(
                f"Image too small after preprocessing: {w}x{h}. "
                f"Minimum dimension is {MIN_DIMENSION}px."
            )


def load_and_prepare(
    source: str | Path | bytes,
    max_dimension: int = MAX_DIMENSION,
    denoise: bool = True,
) -> PreparedImage:
    """Convenience wrapper for one-shot preprocessing."""
    preprocessor = ImagePreprocessor(max_dimension=max_dimension, denoise=denoise)
    return preprocessor.prepare(source)
