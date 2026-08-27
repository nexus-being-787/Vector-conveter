import { useState } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Maximize2, Eye } from 'lucide-react';
import { useImageViewer } from '../hooks/useImageViewer';
import { previewUrl, svgUrl } from '../services/api';

type ViewMode = 'original' | 'vector' | 'paths';

interface Props {
  imageId?: string;
  svgId?: string;
  hasAlpha?: boolean;
}

export function SideBySideViewer({ imageId, svgId, hasAlpha }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('original');
  const leftViewer = useImageViewer();
  const rightViewer = useImageViewer();
  const [synced, setSynced] = useState(false);

  const VIEW_MODES: { value: ViewMode; label: string }[] = [
    { value: 'original', label: 'Original' },
    { value: 'vector',   label: 'Vector' },
    { value: 'paths',    label: 'Paths' },
  ];

  return (
    <div className="card overflow-hidden flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5 flex-wrap">
        {/* View mode tabs */}
        <div className="flex gap-1 bg-surface-700 rounded-lg p-1 mr-2">
          {VIEW_MODES.map(m => (
            <button
              key={m.value}
              onClick={() => setViewMode(m.value)}
              className={[
                'px-3 py-1 rounded-md text-xs font-medium transition-all',
                viewMode === m.value
                  ? 'bg-forge-500 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200',
              ].join(' ')}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Sync toggle */}
        <button
          onClick={() => setSynced(s => !s)}
          className={`btn-ghost text-xs ${synced ? 'text-forge-400' : ''}`}
        >
          <Eye className="w-3.5 h-3.5" />
          {synced ? 'Synced' : 'Sync Zoom'}
        </button>

        <div className="ml-auto flex items-center gap-1">
          {/* Left panel controls */}
          <button onClick={leftViewer.zoomIn} className="btn-ghost px-2 py-1" title="Zoom in left">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button onClick={leftViewer.zoomOut} className="btn-ghost px-2 py-1" title="Zoom out left">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => { leftViewer.reset(); rightViewer.reset(); }} className="btn-ghost px-2 py-1" title="Reset view">
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Panels */}
      <div className="flex flex-1 min-h-0 divide-x divide-white/5" style={{ height: '480px' }}>
        {/* LEFT: Original */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center justify-between px-3 py-1.5 bg-surface-700/50">
            <span className="text-xs text-slate-400 font-medium">Original</span>
            {imageId && (
              <span className="text-xs font-mono text-slate-500 bg-surface-600 px-2 py-0.5 rounded">
                raster
              </span>
            )}
          </div>
          <div
            id="viewer-left"
            className={`flex-1 viewer-panel ${hasAlpha ? 'checker-bg' : 'bg-surface-800'} flex items-center justify-center overflow-hidden`}
            onWheel={leftViewer.onWheel}
            onMouseDown={leftViewer.onMouseDown}
            onMouseMove={leftViewer.onMouseMove}
            onMouseUp={leftViewer.onMouseUp}
            onMouseLeave={leftViewer.onMouseUp}
          >
            {imageId ? (
              <img
                src={previewUrl(imageId)}
                alt="Original"
                draggable={false}
                className="max-w-none select-none"
                style={{
                  transform: `translate(${leftViewer.transform.x}px, ${leftViewer.transform.y}px) scale(${leftViewer.transform.scale})`,
                  maxWidth: '100%',
                  maxHeight: '100%',
                  objectFit: 'contain',
                }}
              />
            ) : (
              <div className="text-slate-500 text-sm">No image loaded</div>
            )}
          </div>
        </div>

        {/* RIGHT: Vector */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center justify-between px-3 py-1.5 bg-surface-700/50">
            <span className="text-xs text-slate-400 font-medium">Vector Result</span>
            {svgId && (
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                SVG
              </span>
            )}
          </div>
          <div
            id="viewer-right"
            className={[
              'flex-1 viewer-panel flex items-center justify-center overflow-hidden',
              svgId ? 'checker-bg' : 'bg-surface-800',
              viewMode === 'paths' ? 'bg-slate-950' : '',
            ].join(' ')}
            onWheel={rightViewer.onWheel}
            onMouseDown={rightViewer.onMouseDown}
            onMouseMove={rightViewer.onMouseMove}
            onMouseUp={rightViewer.onMouseUp}
            onMouseLeave={rightViewer.onMouseUp}
          >
            {svgId ? (
              <object
                data={`${svgUrl(svgId)}${viewMode === 'paths' ? '?mode=paths' : ''}`}
                type="image/svg+xml"
                draggable={false}
                className="select-none"
                style={{
                  transform: `translate(${rightViewer.transform.x}px, ${rightViewer.transform.y}px) scale(${rightViewer.transform.scale})`,
                  maxWidth: '100%',
                  maxHeight: '100%',
                }}
              />
            ) : (
              <div className="flex flex-col items-center gap-3 text-slate-500">
                <div className="w-16 h-16 rounded-2xl border-2 border-dashed border-white/10 flex items-center justify-center">
                  <Maximize2 className="w-6 h-6" />
                </div>
                <p className="text-sm">SVG will appear here</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer zoom indicators */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-white/5 text-xs text-slate-500">
        <span>Left: {Math.round(leftViewer.transform.scale * 100)}%</span>
        <span className="text-slate-600">scroll to zoom · drag to pan</span>
        <span>Right: {Math.round(rightViewer.transform.scale * 100)}%</span>
      </div>
    </div>
  );
}
