"""
VectorForge — FastAPI Routes
Endpoints: /upload, /analyze, /vectorize, /preview, /download, /cleanup
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.api.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    BackgroundHandling,
    ColorCount,
    ErrorResponse,
    UploadResponse,
    VectorizeRequest,
    VectorizeResponse,
)
from backend.preprocessing.image_prep import ImagePreprocessor
from backend.analysis.image_analysis import ImageAnalyzer
from backend.vectorizer.pipeline import (
    PipelineConfig,
    VectorizationMode,
    VectorizationPipeline,
)
from backend.vectorizer.pipeline import BackgroundHandling as PipelineBG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# In-memory store: image_id → file paths + metadata
# In production, replace with Redis or a proper session store.
_sessions: dict = {}

UPLOAD_DIR = Path("./tmp/uploads")
SVG_DIR = Path("./tmp/svgs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SVG_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Validate and store an uploaded image. Returns image_id for subsequent calls."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Accepted: PNG, JPEG, WebP"
        )

    # Read and size-check
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // 1024} KB). Max is 50 MB."
        )

    # Preprocess to validate and get dimensions
    try:
        preprocessor = ImagePreprocessor(denoise=False)
        prepared = preprocessor.prepare(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Persist file
    image_id = str(uuid.uuid4())
    ext = Path(file.filename or "image.png").suffix.lower() or ".png"
    file_path = UPLOAD_DIR / f"{image_id}{ext}"
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    _sessions[image_id] = {
        "file_path": str(file_path),
        "filename": file.filename,
        "original_bytes": len(content),
        "width": prepared.processed_size[0],
        "height": prepared.processed_size[1],
        "has_alpha": prepared.has_alpha,
        "color_mode": prepared.color_mode,
        "analysis": None,
        "svg_id": None,
    }

    return UploadResponse(
        image_id=image_id,
        filename=file.filename or "image",
        original_bytes=len(content),
        width=prepared.processed_size[0],
        height=prepared.processed_size[1],
        has_alpha=prepared.has_alpha,
        color_mode=prepared.color_mode,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Analyze
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(body: AnalysisRequest):
    """Run image analysis on a previously uploaded image."""
    session = _get_session(body.image_id)

    # Re-run preprocessing (with denoise) then analysis
    async with aiofiles.open(session["file_path"], "rb") as f:
        content = await f.read()

    preprocessor = ImagePreprocessor()
    prepared = preprocessor.prepare(content)

    analyzer = ImageAnalyzer()
    result = analyzer.analyze(prepared)

    session["analysis"] = result

    return AnalysisResponse(
        image_id=body.image_id,
        width=result.width,
        height=result.height,
        aspect_ratio=result.aspect_ratio,
        dominant_color_count=result.dominant_color_count,
        color_entropy=result.color_entropy,
        edge_density=result.edge_density,
        image_complexity=result.image_complexity,
        transparency_percentage=result.transparency_percentage,
        estimated_vector_complexity=result.estimated_vector_complexity,
        classification=result.classification.value,
        dominant_colors=["#{:02x}{:02x}{:02x}".format(*c) for c in result.dominant_colors],
        recommended_colors=result.recommended_colors,
        recommended_detail=result.recommended_detail,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Vectorize (SSE streaming)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/vectorize")
async def vectorize_image(body: VectorizeRequest):
    """
    Full vectorization pipeline with Server-Sent Events progress streaming.
    Returns SSE stream; final event contains the result payload.
    """
    session = _get_session(body.image_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Load image
            async with aiofiles.open(session["file_path"], "rb") as f:
                content = await f.read()

            preprocessor = ImagePreprocessor()
            prepared = preprocessor.prepare(content)

            # Resolve color count
            if body.colors == ColorCount.AUTO:
                num_colors = 0  # triggers auto
                auto = True
            elif body.colors.value.isdigit():
                num_colors = int(body.colors.value)
                auto = False
            else:
                num_colors = body.custom_colors or 32
                auto = False

            if num_colors == 0 or auto:
                num_colors = session.get("analysis", None)
                if num_colors and hasattr(num_colors, "recommended_colors"):
                    num_colors = num_colors.recommended_colors
                else:
                    num_colors = 32

            # Map background handling
            bg_map = {
                BackgroundHandling.KEEP: PipelineBG.KEEP,
                BackgroundHandling.REMOVE: PipelineBG.REMOVE,
                BackgroundHandling.TRANSPARENT: PipelineBG.TRANSPARENT,
                BackgroundHandling.SIMPLIFY: PipelineBG.SIMPLIFY,
            }

            config = PipelineConfig(
                num_colors=num_colors,
                detail_level=body.detail_level,
                mode=VectorizationMode(body.mode.value),
                background_handling=bg_map[body.background_handling],
                use_watershed=body.use_watershed,
                auto_colors=(body.colors == ColorCount.AUTO),
            )

            pipeline = VectorizationPipeline(config=config)

            # Run stages synchronously (CPU-bound) in a thread pool
            loop = asyncio.get_event_loop()

            def run_pipeline():
                events = []
                for event in pipeline.run_with_progress(
                    prepared, session["original_bytes"]
                ):
                    events.append(event)
                return events

            events = await loop.run_in_executor(None, run_pipeline)

            for event in events:
                payload = {
                    "stage": event.stage,
                    "percent": event.percent,
                    "message": event.message,
                    "data": event.data or {},
                }
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0)  # allow other coroutines to run

            # Save SVG
            result = pipeline.last_result
            if result is None:
                yield f"data: {json.dumps({'stage': 'error', 'percent': 0, 'message': 'Pipeline returned no result'})}\n\n"
                return

            svg_id = str(uuid.uuid4())
            svg_path = SVG_DIR / f"{svg_id}.svg"
            async with aiofiles.open(svg_path, "w", encoding="utf-8") as f:
                await f.write(result.optimized_svg)

            session["svg_id"] = svg_id

            # Final result event
            qr = result.quality_report
            final = {
                "stage": "result",
                "percent": 100,
                "message": "Done",
                "data": {
                    "image_id": body.image_id,
                    "svg_id": svg_id,
                    "path_count": result.svg_document.path_count,
                    "color_count": result.svg_document.color_count,
                    "original_bytes": session["original_bytes"],
                    "svg_bytes": result.optimization_report.optimized_bytes,
                    "compression_ratio": round(
                        session["original_bytes"] / max(result.optimization_report.optimized_bytes, 1), 2
                    ),
                    "ssim": qr.ssim if qr else None,
                    "psnr": qr.psnr if qr else None,
                    "edge_similarity": qr.edge_similarity if qr else None,
                    "pixel_coverage": qr.pixel_coverage if qr else None,
                    "reconstruction_score": qr.reconstruction_score if qr else None,
                    "processing_time_ms": result.total_time_ms,
                    "classification": result.analysis.classification.value,
                    "palette_hex": result.analysis.dominant_colors
                        and ["#{:02x}{:02x}{:02x}".format(*c) for c in result.analysis.dominant_colors]
                        or [],
                },
            }
            yield f"data: {json.dumps(final)}\n\n"

        except Exception as exc:
            logger.exception("Pipeline error: %s", exc)
            yield f"data: {json.dumps({'stage': 'error', 'percent': 0, 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Preview / Download
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/preview/{image_id}")
async def preview_original(image_id: str):
    """Serve the original uploaded image."""
    session = _get_session(image_id)
    return FileResponse(session["file_path"])


@router.get("/svg/{svg_id}")
async def get_svg(svg_id: str):
    """Serve a generated SVG file inline (for browser preview)."""
    svg_path = SVG_DIR / f"{svg_id}.svg"
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG not found")
    return FileResponse(
        svg_path,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f"inline; filename={svg_id}.svg"},
    )


@router.get("/download/{svg_id}")
async def download_svg(svg_id: str):
    """Download a generated SVG file as an attachment."""
    svg_path = SVG_DIR / f"{svg_id}.svg"
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG not found")
    return FileResponse(
        svg_path,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f"attachment; filename=vectorforge-{svg_id[:8]}.svg"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/cleanup/{image_id}")
async def cleanup(image_id: str):
    """Remove all temporary files for a session."""
    session = _sessions.pop(image_id, None)
    if session:
        for key in ("file_path",):
            p = Path(session.get(key, ""))
            if p.exists():
                p.unlink(missing_ok=True)
        svg_id = session.get("svg_id")
        if svg_id:
            svg_path = SVG_DIR / f"{svg_id}.svg"
            svg_path.unlink(missing_ok=True)
    return {"status": "cleaned"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_session(image_id: str) -> dict:
    session = _sessions.get(image_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Image ID '{image_id}' not found. Please upload first.")
    return session
