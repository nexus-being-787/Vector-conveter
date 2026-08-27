import { CheckCircle2, Loader2 } from 'lucide-react';
import type { ProgressEvent } from '../services/api';

interface Props {
  events: ProgressEvent[];
  currentPercent: number;
  currentMessage: string;
  stage: string;
}

const STAGE_LABELS: Record<string, string> = {
  analysis:      'Image Analysis',
  quantization:  'Color Quantization',
  segmentation:  'Region Segmentation',
  contours:      'Contour Extraction',
  bezier:        'Bézier Fitting',
  svg_generation:'SVG Generation',
  optimization:  'SVG Optimization',
  evaluation:    'Quality Metrics',
  done:          'Complete',
};

const ALL_STAGES = Object.keys(STAGE_LABELS);

export function ProgressBar({ events, currentPercent, currentMessage, stage }: Props) {
  const stagesReached = new Set(events.map(e => e.stage));

  return (
    <div className="card p-5 space-y-4 animate-fade-in">
      {/* Bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-slate-400">Progress</span>
          <span className="text-xs font-mono font-bold text-forge-300">{currentPercent}%</span>
        </div>
        <div className="h-2 bg-surface-600 rounded-full overflow-hidden">
          <div className="progress-bar-fill h-full rounded-full" style={{ width: `${currentPercent}%` }} />
        </div>
        <p className="mt-1.5 text-xs text-slate-400 truncate">{currentMessage}</p>
      </div>

      {/* Stage checklist */}
      <div className="space-y-1">
        {ALL_STAGES.filter(s => s !== 'done').map(s => {
          const done = stagesReached.has(s);
          const active = stage === s;
          return (
            <div key={s} className="flex items-center gap-2.5 py-0.5">
              {done ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
              ) : active ? (
                <Loader2 className="w-3.5 h-3.5 text-forge-400 animate-spin flex-shrink-0" />
              ) : (
                <span className="w-3.5 h-3.5 rounded-full border border-white/10 flex-shrink-0" />
              )}
              <span className={[
                'text-xs',
                done    ? 'text-emerald-400' :
                active  ? 'text-forge-300 font-medium' :
                          'text-slate-500',
              ].join(' ')}>
                {STAGE_LABELS[s]}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
