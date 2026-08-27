import { useState } from 'react';
import { Sliders, Palette, Layers, ImageOff, Play, RotateCcw, ChevronDown } from 'lucide-react';
import type { AnalysisResponse } from '../services/api';
import type { VectorizeOptions } from '../services/api';

interface Props {
  analysis?: AnalysisResponse;
  onVectorize: (opts: Omit<VectorizeOptions, 'image_id'>) => void;
  onReset: () => void;
  disabled?: boolean;
  stage: string;
}

const COLOR_OPTIONS = [
  { value: 'auto', label: 'Auto (recommended)' },
  { value: '8',   label: '8 colors' },
  { value: '16',  label: '16 colors' },
  { value: '32',  label: '32 colors' },
  { value: '64',  label: '64 colors' },
  { value: '128', label: '128 colors' },
  { value: '256', label: '256 colors' },
];

const MODE_OPTIONS = [
  { value: 'auto',         label: 'Auto Detect' },
  { value: 'icon',         label: 'Icon / Simple' },
  { value: 'logo',         label: 'Logo' },
  { value: 'illustration', label: 'Illustration' },
  { value: 'portrait',     label: 'Portrait' },
  { value: 'photograph',   label: 'Photograph' },
];

const BG_OPTIONS = [
  { value: 'keep',        label: 'Keep Background' },
  { value: 'remove',      label: 'Remove Background' },
  { value: 'transparent', label: 'Transparent' },
  { value: 'simplify',    label: 'Simplify' },
];

export function ControlsPanel({ analysis, onVectorize, onReset, disabled, stage }: Props) {
  const [mode, setMode] = useState('auto');
  const [colors, setColors] = useState('auto');
  const [detail, setDetail] = useState(analysis?.recommended_detail ?? 5);
  const [background, setBackground] = useState('keep');
  const [watershed, setWatershed] = useState(false);

  const isRunning = stage === 'vectorizing';
  const isDone = stage === 'done';

  const handleVectorize = () => {
    onVectorize({ mode, colors, detail_level: detail, background_handling: background, use_watershed: watershed });
  };

  return (
    <div className="card p-5 space-y-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-pink-500/20 flex items-center justify-center">
          <Sliders className="w-4 h-4 text-pink-400" />
        </div>
        <span className="font-semibold text-sm text-slate-100">Vectorization Controls</span>
      </div>

      {/* Mode */}
      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-xs font-medium text-slate-400">
          <Layers className="w-3.5 h-3.5" /> Mode
        </label>
        <div className="relative">
          <select
            id="mode-select"
            className="select pr-8 appearance-none"
            value={mode}
            onChange={e => setMode(e.target.value)}
            disabled={disabled || isRunning}
          >
            {MODE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <ChevronDown className="absolute right-2.5 top-2.5 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Color count */}
      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-xs font-medium text-slate-400">
          <Palette className="w-3.5 h-3.5" /> Colors
          {analysis && <span className="ml-auto text-forge-400 font-mono">rec: {analysis.recommended_colors}</span>}
        </label>
        <div className="relative">
          <select
            id="colors-select"
            className="select pr-8"
            value={colors}
            onChange={e => setColors(e.target.value)}
            disabled={disabled || isRunning}
          >
            {COLOR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <ChevronDown className="absolute right-2.5 top-2.5 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Detail slider */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-medium text-slate-400">Detail Level</label>
          <span className="text-xs font-mono font-bold text-forge-300">{detail}/10</span>
        </div>
        <input
          id="detail-slider"
          type="range"
          min={1}
          max={10}
          step={1}
          value={detail}
          onChange={e => setDetail(Number(e.target.value))}
          disabled={disabled || isRunning}
          className="w-full h-1.5 appearance-none bg-surface-600 rounded-full
                     accent-forge-500 cursor-pointer disabled:opacity-40"
        />
        <div className="flex justify-between text-xs text-slate-500">
          <span>Low (fast)</span>
          <span>High (detailed)</span>
        </div>
      </div>

      {/* Background */}
      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-xs font-medium text-slate-400">
          <ImageOff className="w-3.5 h-3.5" /> Background
        </label>
        <div className="grid grid-cols-2 gap-1.5">
          {BG_OPTIONS.map(o => (
            <button
              key={o.value}
              id={`bg-${o.value}`}
              onClick={() => setBackground(o.value)}
              disabled={disabled || isRunning}
              className={[
                'text-xs px-2.5 py-1.5 rounded-lg border transition-all duration-150',
                background === o.value
                  ? 'bg-forge-500/20 border-forge-500/50 text-forge-300 font-semibold'
                  : 'bg-surface-700 border-white/10 text-slate-400 hover:border-white/20',
                (disabled || isRunning) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
              ].join(' ')}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Advanced toggle */}
      <div className="flex items-center justify-between card-inner px-4 py-2.5">
        <span className="text-xs text-slate-400">Watershed Refinement</span>
        <button
          id="watershed-toggle"
          onClick={() => setWatershed(v => !v)}
          disabled={disabled || isRunning}
          className={[
            'w-10 h-5 rounded-full transition-all duration-200 relative',
            watershed ? 'bg-forge-500' : 'bg-surface-500',
            (disabled || isRunning) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
          ].join(' ')}
        >
          <span className={[
            'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all duration-200',
            watershed ? 'left-5' : 'left-0.5',
          ].join(' ')} />
        </button>
      </div>

      {/* Actions */}
      <div className="space-y-2 pt-1">
        <button
          id="vectorize-btn"
          onClick={handleVectorize}
          disabled={disabled || isRunning}
          className="btn-primary w-full justify-center text-base py-3"
        >
          {isRunning ? (
            <>
              <span className="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />
              Vectorizing…
            </>
          ) : isDone ? (
            <><Play className="w-4 h-4" /> Vectorize Again</>
          ) : (
            <><Play className="w-4 h-4" /> Generate SVG</>
          )}
        </button>

        <button
          id="reset-btn"
          onClick={onReset}
          className="btn-secondary w-full justify-center"
          disabled={isRunning}
        >
          <RotateCcw className="w-3.5 h-3.5" /> Start Over
        </button>
      </div>
    </div>
  );
}
