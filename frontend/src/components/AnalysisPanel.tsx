import { BarChart2, Layers, Palette, Zap, AlertCircle } from 'lucide-react';
import type { AnalysisResponse } from '../services/api';

interface Props {
  analysis: AnalysisResponse;
  upload: { filename: string; original_bytes: number; width: number; height: number };
}

const CLASS_BADGE: Record<string, string> = {
  ICON: 'badge-blue',
  LOGO: 'badge-blue',
  FLAT_GRAPHIC: 'badge-green',
  ILLUSTRATION: 'badge-green',
  PORTRAIT: 'badge-pink',
  PHOTOGRAPH: 'badge-amber',
  COMPLEX: 'badge-amber',
};

const COMPLEXITY_COLOR: Record<string, string> = {
  LOW: 'text-emerald-400',
  MEDIUM: 'text-amber-400',
  HIGH: 'text-orange-400',
  'VERY HIGH': 'text-rose-400',
};

function MiniBar({ value, max = 1, color = 'bg-forge-500' }: {
  value: number; max?: number; color?: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex-1 h-1.5 bg-surface-600 rounded-full overflow-hidden">
      <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function AnalysisPanel({ analysis, upload }: Props) {
  const badgeClass = CLASS_BADGE[analysis.classification] ?? 'badge-blue';
  const complexColor = COMPLEXITY_COLOR[analysis.estimated_vector_complexity] ?? 'text-slate-300';

  const kb = (n: number) => n >= 1024 ? `${(n / 1024).toFixed(1)} MB` : `${Math.round(n)} KB`;

  return (
    <div className="card p-5 space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-forge-500/20 flex items-center justify-center">
            <BarChart2 className="w-4 h-4 text-forge-400" />
          </div>
          <span className="font-semibold text-sm text-slate-100">Image Analysis</span>
        </div>
        <span className={`badge ${badgeClass}`}>{analysis.classification}</span>
      </div>

      {/* File info */}
      <div className="card-inner px-4 py-3 space-y-1">
        <p className="text-xs font-mono text-slate-300 truncate">{upload.filename}</p>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span>{analysis.width} × {analysis.height} px</span>
          <span>·</span>
          <span>AR {analysis.aspect_ratio.toFixed(2)}</span>
          <span>·</span>
          <span>{kb(upload.original_bytes)}</span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: 'Dominant Colors', value: analysis.dominant_color_count, icon: Palette },
          { label: 'Recommended Colors', value: analysis.recommended_colors, icon: Layers },
          { label: 'Recommended Detail', value: `${analysis.recommended_detail}/10`, icon: Zap },
          { label: 'Transparency', value: `${analysis.transparency_percentage.toFixed(1)}%`, icon: AlertCircle },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="card-inner px-3 py-2.5">
            <Icon className="w-3.5 h-3.5 text-slate-400 mb-1" />
            <div className="text-base font-bold text-slate-100">{value}</div>
            <div className="text-xs text-slate-400">{label}</div>
          </div>
        ))}
      </div>

      {/* Meter bars */}
      <div className="space-y-2">
        {[
          { label: 'Color Entropy', value: analysis.color_entropy, max: 12, color: 'bg-forge-500' },
          { label: 'Edge Density', value: analysis.edge_density, max: 0.2, color: 'bg-pink-500' },
          { label: 'Image Complexity', value: analysis.image_complexity, max: 1, color: 'bg-amber-500' },
        ].map(({ label, value, max, color }) => (
          <div key={label} className="flex items-center gap-3">
            <span className="text-xs text-slate-400 w-28 flex-shrink-0">{label}</span>
            <MiniBar value={value} max={max} color={color} />
            <span className="text-xs font-mono text-slate-300 w-10 text-right flex-shrink-0">
              {value.toFixed(3)}
            </span>
          </div>
        ))}
      </div>

      {/* Vector complexity */}
      <div className="flex items-center justify-between card-inner px-4 py-2">
        <span className="text-xs text-slate-400">Est. Vector Complexity</span>
        <span className={`text-xs font-bold ${complexColor}`}>
          {analysis.estimated_vector_complexity}
        </span>
      </div>

      {/* Dominant color swatches */}
      {analysis.dominant_colors.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-2">Dominant Colors</p>
          <div className="flex flex-wrap gap-1.5">
            {analysis.dominant_colors.slice(0, 24).map((hex, i) => (
              <div
                key={i}
                className="palette-swatch"
                style={{ backgroundColor: hex }}
                title={hex}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
