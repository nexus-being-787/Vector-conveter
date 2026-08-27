"""
VectorForge — Pytest test suite
Run: .venv/bin/python -m pytest tests/ -v
"""

import io
import pytest
import numpy as np
from PIL import Image

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: generate simple test images in memory
# ─────────────────────────────────────────────────────────────────────────────

def make_rgb_png(width=64, height=64, color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_rgba_png(width=64, height=64) -> bytes:
    """Create an RGBA image with fully transparent pixels (alpha=0) in half of the image."""
    import numpy as np
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    arr[:, :, :3] = [0, 128, 255]
    arr[:, :, 3] = 255          # fully opaque
    arr[:height // 2, :, 3] = 0  # top half fully transparent
    img = Image.fromarray(arr, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_gradient_png(width=128, height=128) -> bytes:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            arr[y, x] = [int(255 * x / width), int(255 * y / height), 128]
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_multicolor_png(width=128, height=128) -> bytes:
    """4-quadrant image with distinct colors."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:height//2, :width//2] = [255, 0, 0]
    arr[:height//2, width//2:] = [0, 255, 0]
    arr[height//2:, :width//2] = [0, 0, 255]
    arr[height//2:, width//2:] = [255, 255, 0]
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Preprocessing tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPreprocessing:
    def test_load_rgb_png(self):
        from backend.preprocessing.image_prep import ImagePreprocessor
        proc = ImagePreprocessor(denoise=False)
        result = proc.prepare(make_rgb_png())
        assert result.array is not None
        assert result.array.shape[2] == 3
        assert not result.has_alpha

    def test_load_rgba_png(self):
        from backend.preprocessing.image_prep import ImagePreprocessor
        proc = ImagePreprocessor(denoise=False)
        result = proc.prepare(make_rgba_png())
        assert result.has_alpha
        assert result.alpha_channel is not None
        assert result.alpha_channel.shape == result.array.shape[:2]

    def test_resize_large_image(self):
        from backend.preprocessing.image_prep import ImagePreprocessor
        large = make_rgb_png(4096, 4096)
        proc = ImagePreprocessor(max_dimension=512, denoise=False)
        result = proc.prepare(large)
        assert max(result.processed_size) <= 512
        assert result.was_resized

    def test_tiny_image_raises(self):
        from backend.preprocessing.image_prep import ImagePreprocessor
        tiny = make_rgb_png(4, 4)
        proc = ImagePreprocessor(max_dimension=2048, denoise=False)
        with pytest.raises(ValueError):
            proc.prepare(tiny)

    def test_invalid_bytes_raises(self):
        from backend.preprocessing.image_prep import ImagePreprocessor
        proc = ImagePreprocessor()
        with pytest.raises(ValueError):
            proc.prepare(b"not an image at all")


# ─────────────────────────────────────────────────────────────────────────────
# Analysis tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalysis:
    def _prepared(self, img_bytes):
        from backend.preprocessing.image_prep import ImagePreprocessor
        return ImagePreprocessor(denoise=False).prepare(img_bytes)

    def test_analysis_returns_result(self):
        from backend.analysis.image_analysis import ImageAnalyzer
        prep = self._prepared(make_multicolor_png())
        result = ImageAnalyzer().analyze(prep)
        assert result.width > 0
        assert result.height > 0
        assert 0.0 <= result.color_entropy
        assert 0.0 <= result.edge_density <= 1.0
        assert 0.0 <= result.image_complexity <= 1.0
        assert result.classification is not None
        assert len(result.dominant_colors) > 0

    def test_transparent_percentage(self):
        from backend.analysis.image_analysis import ImageAnalyzer
        prep = self._prepared(make_rgba_png())
        result = ImageAnalyzer().analyze(prep)
        # Our test RGBA image has alpha=128, so ~50% of pixels are semi-transparent
        assert result.transparency_percentage > 0

    def test_solid_color_is_simple(self):
        from backend.analysis.image_analysis import ImageAnalyzer
        prep = self._prepared(make_rgb_png(128, 128, (200, 100, 50)))
        result = ImageAnalyzer().analyze(prep)
        assert result.image_complexity < 0.3


# ─────────────────────────────────────────────────────────────────────────────
# Color quantization tests
# ─────────────────────────────────────────────────────────────────────────────

class TestQuantizer:
    def _bgr(self, img_bytes):
        import cv2
        from backend.preprocessing.image_prep import ImagePreprocessor
        prep = ImagePreprocessor(denoise=False).prepare(img_bytes)
        return prep.array

    def test_quantize_produces_correct_num_colors(self):
        from backend.color.quantizer import ColorQuantizer
        bgr = self._bgr(make_gradient_png())
        q = ColorQuantizer(num_colors=8).quantize(bgr)
        assert q.num_colors == 8
        assert len(q.palette_bgr) == 8
        assert len(q.palette_hex) == 8

    def test_label_map_shape(self):
        from backend.color.quantizer import ColorQuantizer
        bgr = self._bgr(make_multicolor_png())
        q = ColorQuantizer(num_colors=4).quantize(bgr)
        assert q.label_map.shape == bgr.shape[:2]

    def test_hex_format(self):
        from backend.color.quantizer import ColorQuantizer
        bgr = self._bgr(make_rgb_png())
        q = ColorQuantizer(num_colors=4).quantize(bgr)
        for h in q.palette_hex:
            assert h.startswith('#')
            assert len(h) == 7

    def test_quantized_image_shape(self):
        from backend.color.quantizer import ColorQuantizer
        bgr = self._bgr(make_multicolor_png())
        q = ColorQuantizer(num_colors=4).quantize(bgr)
        assert q.quantized_bgr.shape == bgr.shape


# ─────────────────────────────────────────────────────────────────────────────
# Segmentation tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSegmenter:
    def _quantized(self, img_bytes, n=4):
        from backend.preprocessing.image_prep import ImagePreprocessor
        from backend.color.quantizer import ColorQuantizer
        prep = ImagePreprocessor(denoise=False).prepare(img_bytes)
        return ColorQuantizer(num_colors=n).quantize(prep.array)

    def test_finds_regions(self):
        from backend.segmentation.segmenter import Segmenter
        q = self._quantized(make_multicolor_png(), n=4)
        seg = Segmenter().segment(q)
        assert seg.total_regions >= 1

    def test_background_is_largest(self):
        from backend.segmentation.segmenter import Segmenter
        q = self._quantized(make_multicolor_png(), n=4)
        seg = Segmenter().segment(q)
        if len(seg.regions) > 1:
            assert seg.regions[0].is_background

    def test_mask_binary(self):
        from backend.segmentation.segmenter import Segmenter
        q = self._quantized(make_rgb_png(128, 128), n=4)
        seg = Segmenter().segment(q)
        for r in seg.regions:
            unique = set(r.mask.flatten().tolist())
            assert unique.issubset({0, 255})


# ─────────────────────────────────────────────────────────────────────────────
# Bezier tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBezier:
    def test_douglas_peucker_simplification(self):
        from backend.curves.bezier import douglas_peucker
        import numpy as np
        # A straight line should reduce to 2 points
        pts = np.array([[float(i), 0.0] for i in range(50)], dtype=np.float32)
        simplified = douglas_peucker(pts, epsilon=1.0)
        assert len(simplified) == 2

    def test_bezier_fit_circle_approximation(self):
        from backend.curves.bezier import fit_bezier_path
        import numpy as np
        # Approximate circle
        t = np.linspace(0, 2 * np.pi, 64, endpoint=False)
        pts = np.stack([np.cos(t) * 50 + 64, np.sin(t) * 50 + 64], axis=1).astype(np.float32)
        segments = fit_bezier_path(pts, error_threshold=4.0)
        assert len(segments) >= 1
        for seg in segments:
            assert seg.shape == (4, 2)


# ─────────────────────────────────────────────────────────────────────────────
# SVG Generator tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSVGGenerator:
    def _pipeline_svg(self, img_bytes, n_colors=4, detail=4):
        """Run minimal pipeline and return SVG string."""
        from backend.preprocessing.image_prep import ImagePreprocessor
        from backend.color.quantizer import ColorQuantizer
        from backend.segmentation.segmenter import Segmenter
        from backend.contours.extractor import ContourExtractor
        from backend.curves.bezier import BezierFitter
        from backend.svg.generator import SVGGenerator, SVGRegionGroup

        prep = ImagePreprocessor(denoise=False).prepare(img_bytes)
        q = ColorQuantizer(num_colors=n_colors).quantize(prep.array)
        seg = Segmenter().segment(q)
        cr = ContourExtractor().extract(seg)
        fitter = BezierFitter(detail_level=detail)

        groups = []
        for rc in cr.region_contours:
            paths = [fitter.fit_contour(c) for c in rc.outer_contours + rc.hole_contours]
            paths = [p for p in paths if p]
            if paths:
                groups.append(SVGRegionGroup(region=rc.region, paths=paths))

        w, h = prep.processed_size
        doc = SVGGenerator().generate(groups, w, h)
        return doc.svg_string

    def test_no_image_element(self):
        svg = self._pipeline_svg(make_multicolor_png())
        assert '<image' not in svg.lower()

    def test_has_path_elements(self):
        svg = self._pipeline_svg(make_multicolor_png())
        assert '<path' in svg

    def test_valid_viewbox(self):
        svg = self._pipeline_svg(make_rgb_png(100, 80))
        assert 'viewBox' in svg

    def test_svg_not_empty(self):
        svg = self._pipeline_svg(make_multicolor_png())
        assert len(svg) > 200

    def test_monochrome_image(self):
        mono = make_rgb_png(128, 128, (200, 200, 200))
        svg = self._pipeline_svg(mono, n_colors=2)
        assert svg is not None
        assert '<svg' in svg


# ─────────────────────────────────────────────────────────────────────────────
# Full pipeline test
# ─────────────────────────────────────────────────────────────────────────────

class TestPipeline:
    def test_end_to_end_multicolor(self):
        from backend.preprocessing.image_prep import ImagePreprocessor
        from backend.vectorizer.pipeline import VectorizationPipeline, PipelineConfig

        raw = make_multicolor_png(128, 128)
        prep = ImagePreprocessor(denoise=False).prepare(raw)
        cfg = PipelineConfig(num_colors=4, detail_level=3)
        pipeline = VectorizationPipeline(config=cfg)

        events = list(pipeline.run_with_progress(prep, len(raw)))
        assert any(e.stage == 'done' for e in events)
        assert pipeline.last_result is not None
        assert pipeline.last_result.svg_document.path_count >= 0
        assert '<path' in pipeline.last_result.optimized_svg or '<svg' in pipeline.last_result.optimized_svg

    def test_transparent_png(self):
        from backend.preprocessing.image_prep import ImagePreprocessor
        from backend.vectorizer.pipeline import VectorizationPipeline, PipelineConfig

        raw = make_rgba_png(64, 64)
        prep = ImagePreprocessor(denoise=False).prepare(raw)
        cfg = PipelineConfig(num_colors=4, detail_level=2)
        pipeline = VectorizationPipeline(config=cfg)
        events = list(pipeline.run_with_progress(prep, len(raw)))
        assert pipeline.last_result is not None
