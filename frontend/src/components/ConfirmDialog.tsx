import { useEffect, useRef } from "react";

type Tone = "primary" | "warning" | "danger" | string;

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  /** 兼容 destructive 风格标识;等价于 tone='danger' */
  destructive?: boolean;
  /** 语义色:'primary' 默认;'warning' 琥珀;'danger' 玫瑰红 */
  tone?: Tone;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmText = "确定",
  cancelText = "取消",
  destructive = false,
  tone,
  onConfirm,
  onCancel,
}: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const effectiveTone: Tone =
    tone ?? (destructive ? "danger" : "primary");

  const confirmClass = (() => {
    switch (effectiveTone) {
      case "danger":
        return "px-4 py-1.5 rounded bg-rose-600 text-white hover:bg-rose-700 text-sm";
      case "warning":
        return "px-4 py-1.5 rounded bg-amber-600 text-white hover:bg-amber-700 text-sm";
      default:
        return "px-4 py-1.5 rounded bg-primary-600 text-white hover:bg-primary-700 text-sm";
    }
  })();

  useEffect(() => {
    if (open) {
      confirmRef.current?.focus();
    }
  }, [open]);

  if (!open) return null;

  return (
    <div
      data-testid="confirm-dialog"
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-lg shadow-xl p-6 w-full max-w-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold mb-2" data-testid="confirm-title">
          {title}
        </h3>
        <p className="text-slate-600 text-sm mb-5" data-testid="confirm-message">
          {message}
        </p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            data-testid="confirm-cancel"
            className="px-4 py-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 text-sm"
          >
            {cancelText}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            data-testid="confirm-ok"
            className={confirmClass}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
