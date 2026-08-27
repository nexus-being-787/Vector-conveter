"""
VectorForge — API Pydantic Schemas
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class VectorizationMode(str, Enum):
    AUTO = "auto"
    ICON = "icon"
    LOGO = "logo"
    ILLUSTRATION = "illustration"
    PORTRAIT = "portrait"
    PHOTOGRAPH = "photograph"


class BackgroundHandling(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"
    TRANSPARENT = "transparent"
    SIMPLIFY = "simplify"


class ColorCount(str, Enum):
    AUTO = "auto"
    C8 = "8"
    C16 = "16"
    C32 = "32"
    C64 = "64"
    C128 = "128"
    C256 = "256"


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    image_id: str
    filename: str
    original_bytes: int
    width: int
    height: int
    has_alpha: bool
    color_mode: str


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    image_id: str


class AnalysisResponse(BaseModel):
    image_id: str
    width: int
    height: int
    aspect_ratio: float
    dominant_color_count: int
    color_entropy: float
    edge_density: float
    image_complexity: float
    transparency_percentage: float
    estimated_vector_complexity: str
    classification: str
    dominant_colors: List[str]       # hex strings
    recommended_colors: int
    recommended_detail: int


# ─────────────────────────────────────────────────────────────────────────────
# Vectorization
# ─────────────────────────────────────────────────────────────────────────────

class VectorizeRequest(BaseModel):
    image_id: str
    mode: VectorizationMode = VectorizationMode.AUTO
    colors: ColorCount = ColorCount.AUTO
    custom_colors: Optional[int] = Field(None, ge=2, le=256)
    detail_level: int = Field(5, ge=1, le=10)
    background_handling: BackgroundHandling = BackgroundHandling.KEEP
    use_watershed: bool = False


class VectorizeResponse(BaseModel):
    image_id: str
    svg_id: str
    path_count: int
    color_count: int
    original_bytes: int
    svg_bytes: int
    compression_ratio: float
    ssim: Optional[float]
    psnr: Optional[float]
    edge_similarity: Optional[float]
    pixel_coverage: Optional[float]
    reconstruction_score: Optional[float]
    processing_time_ms: float
    classification: str
    palette_hex: List[str]


# ─────────────────────────────────────────────────────────────────────────────
# SSE progress event
# ─────────────────────────────────────────────────────────────────────────────

class ProgressEventSchema(BaseModel):
    stage: str
    percent: int
    message: str
    data: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Error
# ─────────────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
