// VectorForge API service layer
// All API calls go through this typed wrapper.

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface UploadResponse {
  image_id: string;
  filename: string;
  original_bytes: number;
  width: number;
  height: number;
  has_alpha: boolean;
  color_mode: string;
}

export interface AnalysisResponse {
  image_id: string;
  width: number;
  height: number;
  aspect_ratio: number;
  dominant_color_count: number;
  color_entropy: number;
  edge_density: number;
  image_complexity: number;
  transparency_percentage: number;
  estimated_vector_complexity: string;
  classification: string;
  dominant_colors: string[];
  recommended_colors: number;
  recommended_detail: number;
}

export interface VectorizeOptions {
  image_id: string;
  mode?: string;
  colors?: string;
  custom_colors?: number;
  detail_level?: number;
  background_handling?: string;
  use_watershed?: boolean;
}

export interface ProgressEvent {
  stage: string;
  percent: number;
  message: string;
  data?: Record<string, unknown>;
}

export interface VectorizeResult {
  image_id: string;
  svg_id: string;
  path_count: number;
  color_count: number;
  original_bytes: number;
  svg_bytes: number;
  compression_ratio: number;
  ssim?: number;
  psnr?: number;
  edge_similarity?: number;
  pixel_coverage?: number;
  reconstruction_score?: number;
  processing_time_ms: number;
  classification: string;
  palette_hex: string[];
}

// ── Upload ────────────────────────────────────────────────────────────────

export async function uploadImage(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/api/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Upload failed');
  }
  return res.json();
}

// ── Analyze ───────────────────────────────────────────────────────────────

export async function analyzeImage(image_id: string): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_id }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Analysis failed');
  }
  return res.json();
}

// ── Vectorize (SSE) ───────────────────────────────────────────────────────

export function vectorize(
  options: VectorizeOptions,
  onProgress: (e: ProgressEvent) => void,
  onResult: (r: VectorizeResult) => void,
  onError: (msg: string) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${BASE}/api/vectorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? 'Vectorization failed');
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const json = line.slice(6).trim();
            if (!json) continue;
            try {
              const event = JSON.parse(json) as ProgressEvent & { data?: Record<string, unknown> };
              if (event.stage === 'error') {
                onError(event.message);
                return;
              }
              if (event.stage === 'result' && event.data) {
                onResult(event.data as unknown as VectorizeResult);
              } else {
                onProgress(event);
              }
            } catch { /* ignore malformed */ }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        onError((err as Error).message ?? 'Unknown error');
      }
    }
  })();

  return () => controller.abort();
}

// ── URLs ──────────────────────────────────────────────────────────────────

export const previewUrl = (image_id: string) => `${BASE}/api/preview/${image_id}`;
export const svgUrl = (svg_id: string) => `${BASE}/api/svg/${svg_id}`;
export const downloadUrl = (svg_id: string) => `${BASE}/api/download/${svg_id}`;

export async function cleanupSession(image_id: string): Promise<void> {
  await fetch(`${BASE}/api/cleanup/${image_id}`, { method: 'DELETE' });
}
