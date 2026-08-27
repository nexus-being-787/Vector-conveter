import { useRef, useState, useCallback } from 'react';

export interface ViewerTransform {
  scale: number;
  x: number;
  y: number;
}

export function useImageViewer(minScale = 0.1, maxScale = 20) {
  const [transform, setTransform] = useState<ViewerTransform>({ scale: 1, x: 0, y: 0 });
  const dragging = useRef(false);
  const lastPos = useRef({ x: 0, y: 0 });

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.85 : 1 / 0.85;
    setTransform(t => ({
      ...t,
      scale: Math.min(maxScale, Math.max(minScale, t.scale * delta)),
    }));
  }, [maxScale, minScale]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
  }, []);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setTransform(t => ({ ...t, x: t.x + dx, y: t.y + dy }));
  }, []);

  const onMouseUp = useCallback(() => {
    dragging.current = false;
  }, []);

  const reset = useCallback(() => {
    setTransform({ scale: 1, x: 0, y: 0 });
  }, []);

  const zoomIn = useCallback(() => {
    setTransform(t => ({ ...t, scale: Math.min(maxScale, t.scale * 1.3) }));
  }, [maxScale]);

  const zoomOut = useCallback(() => {
    setTransform(t => ({ ...t, scale: Math.max(minScale, t.scale / 1.3) }));
  }, [minScale]);

  return {
    transform,
    setTransform,
    onWheel,
    onMouseDown,
    onMouseMove,
    onMouseUp,
    reset,
    zoomIn,
    zoomOut,
  };
}
