import { TrendingUp, FileDown, Layers, Palette, Clock } from 'lucide-react';
import type { VectorizeResult } from '../services/api';
import { downloadUrl } from '../services/api';

interface Props {
  result: VectorizeResult;
}

function ScoreArc({ score }: { score: number }) {
  const r = 40;
  const circ = 2 * Math.PI * r;
  const dashOffset = circ - (score / 100) * circ;
  const color =
    score >= 75 ? '#34d399' :
    score >= 50 ? '#fbbf24' :
    '#f87171';

  return (
    <div className="relative w-28 h-28 mx-auto">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#252848" strokeWidth="10" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={circ}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-slate-100">{score.toFixed(0)}</span>
        <span className="text-xs text-slate-400">/ 100</span>
      </div>
    </div>
  );
}

function kb(n: number) {
  if (n >= 1024 * 1024) return `${(n / 1024 / 1024).toFixed(2)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

export function MetricsPanel({ result }: Props) {
  const reduction = result.original_bytes > 0
    ? Math.max(0, (1 - result.svg_bytes / result.original_bytes) * 100)
    : 0;

  return (
    <div className="card p-5 space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
        </div>
        <span className="font-semibold text-sm text-slate-100">Quality Metrics</span>
        <span className="badge badge-green ml-auto">{result.classification}</span>
      </div>

      {/* Score arc */}
      {result.reconstruction_score != null && (
        <div className="text-center space-y-1">
          <ScoreArc score={result.reconstruction_score} />
          <p className="text-xs text-slate-400">Reconstruction Score</p>
        </div>
      )}

      {/* Stats */}
      <div className="space-y-0">
        {result.ssim != null && (
          <div className="stat-row">
            <span className="stat-label">SSIM</span>
            <span className="stat-value">{result.ssim.toFixed(4)}</span>
          </div>
        )}
        {result.psnr != null && (
          <div className="stat-row">
            <span className="stat-label">PSNR</span>
            <span className="stat-value">{result.psnr.toFixed(1)} dB</span>
          </div>
        )}
        {result.edge_similarity != null && (
          <div className="stat-row">
            <span className="stat-label">Edge Similarity</span>
            <span className="stat-value">{(result.edge_similarity * 100).toFixed(1)}%</span>
          </div>
        )}
        {result.pixel_coverage != null && (
          <div className="stat-row">
            <span className="stat-label">Pixel Coverage</span>
            <span className="stat-value">{(result.pixel_coverage * 100).toFixed(1)}%</span>
          </div>
        )}
      </div>

      {/* Size comparison */}
      <div className="card-inner px-4 py-3 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400">Original PNG</span>
          <span className="font-mono text-slate-300">{kb(result.original_bytes)}</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400">Generated SVG</span>
          <span className="font-mono text-emerald-300">{kb(result.svg_bytes)}</span>
        </div>
        <div className="h-px bg-white/5" />
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400">Size reduction</span>
          <span className="font-bold text-emerald-400">{reduction.toFixed(1)}% smaller</span>
        </div>
      </div>

      {/* Path & color counts */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { icon: Layers, label: 'Paths', value: result.path_count },
          { icon: Palette, label: 'Colors', value: result.color_count },
          { icon: Clock, label: 'Time', value: `${(result.processing_time_ms / 1000).toFixed(1)}s` },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="card-inner px-2 py-2 text-center">
            <Icon className="w-3.5 h-3.5 text-slate-400 mx-auto mb-1" />
            <div className="text-base font-bold text-slate-100">{value}</div>
            <div className="text-xs text-slate-400">{label}</div>
          </div>
        ))}
      </div>

      {/* Palette */}
      {result.palette_hex && result.palette_hex.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-2">Output Palette</p>
          <div className="flex flex-wrap gap-1.5">
            {result.palette_hex.slice(0, 32).map((hex, i) => (
              <div key={i} className="palette-swatch" style={{ backgroundColor: hex }} title={hex} />
            ))}
          </div>
        </div>
      )}

      {/* Download button */}
      <a
        id="download-svg-btn"
        href={downloadUrl(result.svg_id)}
        download={`vectorforge-${result.svg_id.slice(0, 8)}.svg`}
        className="btn-primary w-full justify-center"
      >
        <FileDown className="w-4 h-4" />
        Download SVG
      </a>
    </div>
  );
}
