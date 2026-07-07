import { useToastStore } from "@/stores/toast";

const KIND_CLS: Record<string, string> = {
  info: "bg-slate-800 text-white",
  success: "bg-emerald-600 text-white",
  error: "bg-rose-600 text-white",
};

export function ToastViewport() {
  const items = useToastStore((s) => s.items);
  const dismiss = useToastStore((s) => s.dismiss);
  return (
    <div
      data-testid="toast-viewport"
      className="fixed top-4 right-4 z-50 space-y-2 max-w-sm"
    >
      {items.map((it) => (
        <div
          key={it.id}
          data-testid={`toast-${it.kind}`}
          className={`px-4 py-2 rounded shadow-lg text-sm ${KIND_CLS[it.kind] || KIND_CLS.info}`}
        >
          <div className="flex items-start gap-2">
            <span className="flex-1">{it.message}</span>
            <button
              onClick={() => dismiss(it.id)}
              className="opacity-70 hover:opacity-100"
              aria-label="关闭"
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
