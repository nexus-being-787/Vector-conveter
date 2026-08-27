import { useCallback, useState } from 'react';
import { Upload, X } from 'lucide-react';

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

const ACCEPTED = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
const ACCEPTED_EXT = '.png,.jpg,.jpeg,.webp';

export function UploadZone({ onFile, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = (file: File): string | null => {
    if (!ACCEPTED.includes(file.type)) return `Unsupported format. Use PNG, JPG, or WebP.`;
    if (file.size > 50 * 1024 * 1024) return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 50 MB.`;
    return null;
  };

  const handleFile = useCallback((file: File) => {
    const err = validate(file);
    if (err) { setError(err); return; }
    setError(null);
    onFile(file);
  }, [onFile]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const onInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = '';
  }, [handleFile]);

  return (
    <div className="w-full animate-fade-in">
      <label
        id="upload-zone"
        htmlFor="file-input"
        className={[
          'flex flex-col items-center justify-center gap-4',
          'border-2 border-dashed rounded-2xl p-12 cursor-pointer',
          'transition-all duration-300',
          dragging
            ? 'border-forge-400 bg-forge-500/10 glow-forge scale-[1.01]'
            : 'border-white/10 bg-surface-800/50 hover:border-forge-500/60 hover:bg-forge-500/5',
          disabled ? 'opacity-50 pointer-events-none' : '',
        ].join(' ')}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <div className={[
          'w-20 h-20 rounded-2xl flex items-center justify-center',
          'bg-gradient-forge shadow-lg',
          dragging ? 'scale-110' : '',
          'transition-transform duration-300',
        ].join(' ')}>
          <Upload className="w-9 h-9 text-white" strokeWidth={1.5} />
        </div>

        <div className="text-center space-y-1">
          <p className="text-lg font-semibold text-slate-100">
            Drop your image here
          </p>
          <p className="text-sm text-slate-400">
            or <span className="text-forge-400 font-medium underline underline-offset-2">browse</span> to upload
          </p>
          <p className="text-xs text-slate-500 mt-2">
            PNG · JPG · WebP · Up to 50 MB
          </p>
        </div>

        <div className="flex gap-3 text-xs text-slate-500">
          {['Icons', 'Logos', 'Photos', 'Illustrations', 'Portraits'].map(t => (
            <span key={t} className="badge bg-surface-600/80 border border-white/10 text-slate-300 normal-case font-normal">
              {t}
            </span>
          ))}
        </div>

        <input
          id="file-input"
          type="file"
          accept={ACCEPTED_EXT}
          className="hidden"
          onChange={onInputChange}
          disabled={disabled}
        />
      </label>

      {error && (
        <div className="mt-3 flex items-center gap-2 text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-xl px-4 py-2.5 animate-fade-in">
          <X className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <p className="mt-4 text-center text-xs text-slate-500">
        🔒 Your images stay on your device — no external AI APIs
      </p>
    </div>
  );
}
