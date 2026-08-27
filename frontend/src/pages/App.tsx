import { useVectorize } from '../hooks/useVectorize';
import { UploadZone } from '../components/UploadZone';
import { AnalysisPanel } from '../components/AnalysisPanel';
import { ControlsPanel } from '../components/ControlsPanel';
import { SideBySideViewer } from '../components/SideBySideViewer';
import { ProgressBar } from '../components/ProgressBar';
import { MetricsPanel } from '../components/MetricsPanel';
import { Zap, Shield, ChevronRight, AlertCircle } from 'lucide-react';

export default function App() {
  const { state, handleFile, runVectorize, reset } = useVectorize();

  const isWorking = state.stage === 'uploading' || state.stage === 'analyzing' || state.stage === 'vectorizing';

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-surface-900/80 backdrop-blur-xl">
        <div className="max-w-screen-2xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-forge flex items-center justify-center shadow-lg shadow-forge-500/30">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold gradient-text leading-none">VectorForge</h1>
              <p className="text-xs text-slate-400 leading-none mt-0.5">Raster → Vector</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400">
              <Shield className="w-3.5 h-3.5 text-emerald-400" />
              <span>Images stay local</span>
            </div>
            <div className="hidden sm:flex gap-2 text-xs text-slate-500">
              {['PNG', 'JPG', 'WebP'].map(f => (
                <span key={f} className="badge bg-surface-700 border border-white/10 text-slate-300 font-mono">{f}</span>
              ))}
            </div>
            <a
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              className="btn-ghost text-xs"
            >
              API Docs <ChevronRight className="w-3 h-3" />
            </a>
          </div>
        </div>
      </header>

      {/* ── Main content ───────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 sm:px-6 py-8">

        {/* Upload / Hero section */}
        {state.stage === 'idle' && (
          <div className="max-w-2xl mx-auto animate-fade-in">
            {/* Hero text */}
            <div className="text-center mb-10">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-forge-500/10 border border-forge-500/20 text-forge-400 text-xs font-medium mb-4">
                <Zap className="w-3 h-3" /> Classical CV · No external AI APIs
              </div>
              <h2 className="text-4xl sm:text-5xl font-extrabold mb-4 leading-tight">
                Turn <span className="gradient-text">Pixels</span> into
                <br />
                <span className="gradient-text">Editable Geometry</span>
              </h2>
              <p className="text-slate-400 text-lg max-w-lg mx-auto">
                Upload any raster image and get a clean, scalable SVG with
                real vector paths — not an embedded bitmap.
              </p>
            </div>

            <UploadZone onFile={handleFile} disabled={isWorking} />

            {/* Feature grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-10">
              {[
                { title: 'Color Quantization', desc: 'K-Means in LAB space for perceptual accuracy' },
                { title: 'Bézier Fitting', desc: 'Smooth cubic curves, not jagged pixel outlines' },
                { title: 'Portrait Mode', desc: 'Background removal + layered SVG groups' },
                { title: 'Quality Metrics', desc: 'SSIM, PSNR, and reconstruction scoring' },
              ].map(f => (
                <div key={f.title} className="card p-4 space-y-1">
                  <p className="text-xs font-semibold text-slate-200">{f.title}</p>
                  <p className="text-xs text-slate-500">{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Working layout: 3-column */}
        {state.stage !== 'idle' && (
          <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr_320px] gap-4 animate-fade-in">

            {/* Left sidebar */}
            <div className="space-y-4 order-2 xl:order-1">
              {/* Upload again button */}
              <div className="flex items-center gap-2">
                <button onClick={reset} className="btn-ghost text-xs">
                  ← New image
                </button>
                {state.upload && (
                  <span className="text-xs text-slate-400 truncate">{state.upload.filename}</span>
                )}
              </div>

              {/* Analysis */}
              {state.analysis && state.upload && (
                <AnalysisPanel analysis={state.analysis} upload={state.upload} />
              )}

              {/* Uploading / analyzing placeholder */}
              {(state.stage === 'uploading' || state.stage === 'analyzing') && (
                <div className="card p-5 animate-pulse">
                  <div className="h-4 bg-surface-600 rounded w-2/3 mb-3" />
                  <div className="h-3 bg-surface-600 rounded w-full mb-2" />
                  <div className="h-3 bg-surface-600 rounded w-4/5" />
                </div>
              )}
            </div>

            {/* Center: viewer + controls */}
            <div className="space-y-4 order-1 xl:order-2">
              {/* Side-by-side viewer */}
              <SideBySideViewer
                imageId={state.upload?.image_id}
                svgId={state.result?.svg_id}
                hasAlpha={state.upload?.has_alpha}
              />

              {/* Error banner */}
              {state.stage === 'error' && state.error && (
                <div className="flex items-start gap-3 card p-4 border border-rose-500/30 bg-rose-500/5 animate-fade-in">
                  <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-rose-300">Error</p>
                    <p className="text-xs text-rose-400/80 mt-0.5">{state.error}</p>
                  </div>
                </div>
              )}

              {/* Progress (while vectorizing) */}
              {state.stage === 'vectorizing' && (
                <ProgressBar
                  events={state.progress}
                  currentPercent={state.currentProgress}
                  currentMessage={state.currentMessage}
                  stage={state.progress[state.progress.length - 1]?.stage ?? ''}
                />
              )}
            </div>

            {/* Right sidebar */}
            <div className="space-y-4 order-3">
              {/* Controls (always show once image is loaded) */}
              {(state.stage === 'ready' || state.stage === 'done' || state.stage === 'vectorizing' || state.stage === 'error') && (
                <ControlsPanel
                  analysis={state.analysis}
                  onVectorize={runVectorize}
                  onReset={reset}
                  disabled={state.stage === 'vectorizing'}
                  stage={state.stage}
                />
              )}

              {/* Results */}
              {state.stage === 'done' && state.result && (
                <MetricsPanel result={state.result} />
              )}
            </div>
          </div>
        )}
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 mt-auto py-4 px-6">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between text-xs text-slate-500">
          <span>VectorForge v1.0 · Classical CV Pipeline</span>
          <span>All processing happens locally · No data sent externally</span>
        </div>
      </footer>
    </div>
  );
}
