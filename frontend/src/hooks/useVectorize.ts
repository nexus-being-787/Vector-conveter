import { useState, useCallback, useRef } from 'react';
import {
  uploadImage,
  analyzeImage,
  vectorize,
  cleanupSession,
  type UploadResponse,
  type AnalysisResponse,
  type VectorizeResult,
  type ProgressEvent,
  type VectorizeOptions,
} from '../services/api';

export type AppStage = 'idle' | 'uploading' | 'analyzing' | 'ready' | 'vectorizing' | 'done' | 'error';

export interface VectorizeState {
  stage: AppStage;
  upload?: UploadResponse;
  analysis?: AnalysisResponse;
  result?: VectorizeResult;
  progress: ProgressEvent[];
  currentProgress: number;
  currentMessage: string;
  error?: string;
}

export function useVectorize() {
  const [state, setState] = useState<VectorizeState>({
    stage: 'idle',
    progress: [],
    currentProgress: 0,
    currentMessage: '',
  });

  const cancelRef = useRef<(() => void) | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setState({
      stage: 'uploading',
      progress: [],
      currentProgress: 0,
      currentMessage: 'Uploading…',
    });

    try {
      const upload = await uploadImage(file);

      setState(prev => ({
        ...prev,
        stage: 'analyzing',
        upload,
        currentMessage: 'Analyzing image…',
      }));

      const analysis = await analyzeImage(upload.image_id);

      setState(prev => ({
        ...prev,
        stage: 'ready',
        analysis,
        currentMessage: 'Ready',
      }));
    } catch (err: unknown) {
      setState(prev => ({
        ...prev,
        stage: 'error',
        error: (err as Error).message,
      }));
    }
  }, []);

  const runVectorize = useCallback((options: Omit<VectorizeOptions, 'image_id'>) => {
    setState(prev => {
      if (!prev.upload) return prev;
      return {
        ...prev,
        stage: 'vectorizing',
        progress: [],
        currentProgress: 0,
        currentMessage: 'Starting…',
        result: undefined,
        error: undefined,
      };
    });

    setState(prev => {
      if (!prev.upload) return prev;
      const imageId = prev.upload.image_id;

      const cancel = vectorize(
        { image_id: imageId, ...options },
        (event: ProgressEvent) => {
          setState(s => ({
            ...s,
            progress: [...s.progress, event],
            currentProgress: event.percent,
            currentMessage: event.message,
          }));
        },
        (result: VectorizeResult) => {
          setState(s => ({
            ...s,
            stage: 'done',
            result,
            currentProgress: 100,
            currentMessage: 'Done!',
          }));
        },
        (msg: string) => {
          setState(s => ({
            ...s,
            stage: 'error',
            error: msg,
            currentMessage: msg,
          }));
        },
      );

      cancelRef.current = cancel;
      return prev;
    });
  }, []);

  const reset = useCallback(() => {
    cancelRef.current?.();
    setState(prev => {
      if (prev.upload) {
        cleanupSession(prev.upload.image_id).catch(() => {});
      }
      return { stage: 'idle', progress: [], currentProgress: 0, currentMessage: '' };
    });
  }, []);

  return { state, handleFile, runVectorize, reset };
}
