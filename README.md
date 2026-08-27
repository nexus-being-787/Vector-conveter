# VectorForge 🔷

> **Turn pixels into editable geometry.**

VectorForge is a production-quality **raster-to-vector SVG converter** that converts PNG, JPG, and WebP images into clean, scalable, colored SVG artwork — using **real vector paths**, not embedded bitmaps.

## 🔒 Privacy First

> **Your images stay on your device/server and are never sent to external AI APIs.**

All processing happens locally via classical computer vision. Future AI features will be explicitly opt-in.

---

## ✨ Features

| Feature | Status |
|---------|--------|
| PNG / JPG / WebP input | ✅ |
| Transparent PNG (alpha preservation) | ✅ |
| Color quantization in LAB space (K-Means) | ✅ |
| Auto palette sizing (elbow method) | ✅ |
| Region segmentation (connected components) | ✅ |
| Watershed boundary refinement | ✅ |
| Hierarchical contour extraction (outer + holes) | ✅ |
| Douglas-Peucker simplification | ✅ |
| Cubic Bézier curve fitting | ✅ |
| SVG optimization (dedup, precision reduction) | ✅ |
| Quality metrics (SSIM, PSNR, edge similarity) | ✅ |
| Background removal via `rembg` | ✅ |
| Image complexity classification | ✅ |
| REST API (FastAPI) | ✅ |
| SSE progress streaming | ✅ |
| React + TypeScript frontend | ✅ |
| Side-by-side viewer with zoom/pan | ✅ |
| CLI | ✅ |
| 24-test pytest suite | ✅ |

---

## 🚀 Quick Start

### 1. Backend

```bash
cd /path/to/SVG-Vector_Image

# Activate the venv
source .venv/bin/activate

# Start the API server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/api/docs

### 2. Frontend

```bash
cd frontend
npm run dev
```

App: http://localhost:5173

### 3. CLI

```bash
# Basic conversion
python scripts/vectorforge_cli.py icon.png --colors 16 --detail 5

# High-quality illustration
python scripts/vectorforge_cli.py art.jpg --mode illustration --colors 64 --detail 8 --output art.svg

# Portrait with background removal
python scripts/vectorforge_cli.py person.jpg --mode portrait --colors 64 --background remove --output portrait.svg

# Full options
python scripts/vectorforge_cli.py --help
```

---

## 🏗️ Architecture

```
SVG-Vector_Image/
├── backend/
│   ├── main.py                   ← FastAPI entry point
│   ├── api/                      ← REST routes + Pydantic schemas
│   ├── preprocessing/            ← EXIF fix, resize, denoise, alpha
│   ├── analysis/                 ← Entropy, edge density, classification
│   ├── color/                    ← K-Means quantization in LAB space
│   ├── segmentation/             ← Connected components + watershed
│   ├── contours/                 ← Hierarchical contour extraction
│   ├── curves/                   ← Douglas-Peucker + Bézier fitting
│   ├── svg/                      ← SVG assembly + metadata
│   ├── optimization/             ← SVG cleanup + size reduction
│   ├── evaluation/               ← SSIM, PSNR, reconstruction score
│   └── vectorizer/
│       └── pipeline.py           ← Orchestrator + ImageUnderstandingModel ABC
├── frontend/                     ← Vite + React + TypeScript + Tailwind v3
├── scripts/
│   └── vectorforge_cli.py        ← CLI with rich progress bars
├── tests/
│   └── test_pipeline.py          ← 24 pytest tests (100% pass)
├── requirements.txt
└── .venv/                        ← Python virtual environment
```

---

## 🔬 Pipeline Stages

```
Input Image
  │
  ▼  Stage 1: Preprocessing
    EXIF correction · resize (max 2048 px) · denoise · alpha extraction
  │
  ▼  Stage 2: Analysis
    Color entropy · edge density · complexity score · classification
    (ICON / LOGO / FLAT_GRAPHIC / ILLUSTRATION / PORTRAIT / PHOTOGRAPH / COMPLEX)
  │
  ▼  Stage 3: Color Quantization
    MiniBatch K-Means in CIE LAB space
    Palette: 8 / 16 / 32 / 64 / 128 / 256 / Auto / Custom
  │
  ▼  Stage 4: Region Segmentation
    Connected components per palette color
    Morphological closing · minimum area filtering
    Optional watershed boundary refinement
  │
  ▼  Stage 5: Contour Extraction
    RETR_CCOMP: outer boundaries + holes
    Hierarchical SVG group structure
  │
  ▼  Stage 6: Path Simplification + Bézier Fitting
    Douglas-Peucker (adaptive epsilon from detail level 1–10)
    Schneider cubic Bézier fitting
  │
  ▼  Stage 7: SVG Generation
    <svg> with viewBox · <g> groups per region · <path> with C commands
    Hex fill colors · Metadata · No <image> embedding
  │
  ▼  Stage 8: Optimization
    Decimal precision reduction · degenerate path removal
    Redundant attribute cleanup
  │
  ▼  Stage 9: Quality Metrics
    SSIM · PSNR · Edge similarity · Pixel coverage
    Composite reconstruction score 0–100
  │
  ▼
Editable Colored SVG
```

---

## 🤖 AI Extension Points

The architecture is built to accept AI models without rewriting the pipeline:

```python
# Drop in a new model by implementing this interface:
class MySegmentationModel(ImageUnderstandingModel):
    def analyze(self, image: np.ndarray) -> Dict:
        # SAM, CLIP, human parser, depth estimator, etc.
        ...
```

Future models planned: SAM-style segmentation, CLIP image understanding, human body parser.

---

## 🧪 Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
# Expected: 24 passed
```

---

## 📊 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload an image |
| `POST` | `/api/analyze` | Analyze image complexity |
| `POST` | `/api/vectorize` | Full pipeline (SSE streaming) |
| `GET` | `/api/preview/{id}` | Serve original image |
| `GET` | `/api/svg/{svg_id}` | Serve SVG inline |
| `GET` | `/api/download/{svg_id}` | Download SVG attachment |
| `DELETE` | `/api/cleanup/{id}` | Remove temp files |
| `GET` | `/api/docs` | Swagger UI |

---

## 🗺️ Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Done | Color quantization + contour vectorization |
| 2 | ✅ Done | Bézier fitting + path simplification |
| 3 | ✅ Done | Quality/detail controls |
| 4 | ✅ Done | Image classification |
| 5 | ✅ Basic | Watershed segmentation |
| 6 | 🔲 Planned | Portrait/person semantic segmentation |
| 7 | ✅ Done | Layered SVG groups |
| 8 | 🔲 Planned | VTracer benchmark comparison |
