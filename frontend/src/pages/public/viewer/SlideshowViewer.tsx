/** PPT 幻灯片子组件：单页图片居中、上一张/下一张、键盘 ←/→、全屏。
 *
 * 后端已把 PPT 拆成多张 PNG 并保存到磁盘，前端直接按页加载 <img> 显示，
 * 不再依赖 PDF.js，避免 PDF 渲染延迟与移动端内存占用。
 *
 * P-VIEWER 范围：禁止任何"下载到本地"入口。`material.downloadUrl` 不再被引用；
 * 图片关闭右键保存 / 拖拽 / contextmenu。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PublicMaterialItem } from "@/api";

type Props = {
  material: PublicMaterialItem;
  onBack: () => void;
  onLogo: () => void;
};

export function SlideshowViewer({ material, onBack, onLogo }: Props) {
  const imageUrls = material.imageUrls ?? [];
  const total = imageUrls.length;
  const [current, setCurrent] = useState<number>(1);
  const [transitioning, setTransitioning] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // 切页淡入淡出
  const goto = useCallback(
    (page: number) => {
      if (page < 1 || page > total || page === current) return;
      setTransitioning(true);
      window.setTimeout(() => {
        setCurrent(page);
        window.setTimeout(() => setTransitioning(false), 60);
      }, 120);
    },
    [current, total],
  );

  const prev = useCallback(() => goto(current - 1), [goto, current]);
  const next = useCallback(() => goto(current + 1), [goto, current]);

  // 键盘 ←/→
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        prev();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        next();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prev, next]);

  const handleFullscreen = useCallback(() => {
    const el = imgRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else if (el.requestFullscreen) {
      el.requestFullscreen().catch(() => {});
    }
  }, []);

  const handleImgLoad = useCallback(() => setLoading(false), []);
  const handleImgError = useCallback(() => {
    setLoading(false);
    setError("图片加载失败，请刷新重试");
  }, []);

  // 当切页时立即显示 loading 直到新图片 load 完
  useEffect(() => {
    setLoading(true);
  }, [current]);

  // 当素材切换时回到第 1 页
  useEffect(() => {
    setCurrent(1);
  }, [material.id]);

  const isFirst = current <= 1;
  const isLast = current >= total;

  const prevLabel = useMemo(
    () => (isFirst ? "已是第一张" : "上一张"),
    [isFirst],
  );
  const nextLabel = useMemo(
    () => (isLast ? "已是最后一张" : "下一张"),
    [isLast],
  );

  // 早期返回:无可用预览
  if (total === 0) {
    return (
      <main
        data-testid="p-viewer-ppt-root"
        className="min-h-screen flex flex-col bg-slate-900 text-white"
      >
        <header className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 bg-slate-800 shadow-sm">
          <button
            type="button"
            data-testid="p-viewer-logo"
            onClick={onLogo}
            aria-label="返回首页"
            className="text-sm font-semibold text-primary-300 hover:bg-slate-700 px-3 py-1 rounded shrink-0"
          >
            🏠 首页
          </button>
          <button
            type="button"
            data-testid="p-viewer-back-btn"
            onClick={onBack}
            className="text-sm text-slate-100 hover:bg-slate-700 px-3 py-1 rounded"
          >
            ← 返回
          </button>
          <h1
            data-testid="p-viewer-title"
            className="text-base font-medium truncate flex-1"
          >
            {material.name}
          </h1>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-100">
            幻灯片
          </span>
        </header>
        <div className="flex-1 flex items-center justify-center p-6">
          <div
            data-testid="p-viewer-ppt-preview-pending"
            className="text-slate-300 text-center"
          >
            预览尚未生成，请稍后重试
          </div>
        </div>
      </main>
    );
  }

  return (
    <main
      data-testid="p-viewer-ppt-root"
      className="min-h-screen flex flex-col bg-slate-900 text-white"
    >
      <header className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 bg-slate-800 shadow-sm">
        <button
          type="button"
          data-testid="p-viewer-logo"
          onClick={onLogo}
          aria-label="返回首页"
          className="text-sm font-semibold text-primary-300 hover:bg-slate-700 px-3 py-1 rounded shrink-0"
        >
          🏠 首页
        </button>
        <button
          type="button"
          data-testid="p-viewer-back-btn"
          onClick={onBack}
          className="text-sm text-slate-100 hover:bg-slate-700 px-3 py-1 rounded"
        >
          ← 返回
        </button>
        <h1
          data-testid="p-viewer-title"
          className="text-base font-medium truncate flex-1"
        >
          {material.name}
        </h1>
        <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-100">
          幻灯片
        </span>
      </header>

      <div
        data-testid="p-viewer-ppt"
        className="flex-1 flex items-center justify-center p-6 min-h-[60vh]"
      >
        {loading && (
          <div className="text-slate-300">正在加载幻灯片…</div>
        )}
        {error && (
          <div
            data-testid="p-viewer-ppt-error"
            className="text-red-300 text-center"
          >
            {error}
          </div>
        )}
        {!error && (
          <img
            ref={imgRef}
            data-testid="p-viewer-ppt-image"
            src={imageUrls[current - 1]}
            alt={`${material.name} 第 ${current} 页`}
            onLoad={handleImgLoad}
            onError={handleImgError}
            onContextMenu={(e) => e.preventDefault()}
            className="max-w-full max-h-[80vh] bg-white shadow-2xl transition-opacity duration-200 object-contain select-none"
            style={{ opacity: transitioning ? 0 : 1 }}
            draggable={false}
          />
        )}
      </div>

      <div
        data-testid="p-viewer-ppt-controls"
        className="flex items-center justify-center gap-4 py-4"
      >
        <button
          type="button"
          data-testid="p-viewer-ppt-prev"
          onClick={prev}
          disabled={isFirst}
          className="px-4 py-2 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {prevLabel}
        </button>
        <span
          data-testid="p-viewer-ppt-indicator"
          aria-live="polite"
          className="px-3 py-1 rounded bg-slate-800 tabular-nums min-w-[5rem] text-center"
        >
          {current} / {total}
        </span>
        <button
          type="button"
          data-testid="p-viewer-ppt-next"
          onClick={next}
          disabled={isLast}
          className="px-4 py-2 rounded bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {nextLabel}
        </button>
        <button
          type="button"
          data-testid="p-viewer-ppt-fullscreen"
          onClick={handleFullscreen}
          className="px-4 py-2 rounded bg-slate-700 hover:bg-slate-600"
        >
          全屏
        </button>
      </div>
    </main>
  );
}

export default SlideshowViewer;