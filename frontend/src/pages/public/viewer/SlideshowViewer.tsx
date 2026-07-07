/** PPT 幻灯片子组件：单页居中、上一张/下一张、键盘 ←/→、全屏。
 *
 * 后端 LibreOffice 已把 PPT 转成 PDF，前端用 PDF.js 单页渲染实现幻灯片效果。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PublicMaterialItem } from "@/api";
import { getPdfjsLib, renderPageToCanvas } from "@/lib/pdfjs";

type Props = {
  material: PublicMaterialItem;
  onBack: () => void;
  onLogo: () => void;
};

export function SlideshowViewer({ material, onBack, onLogo }: Props) {
  const [current, setCurrent] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState<boolean>(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const docRef = useRef<import("pdfjs-dist").PDFDocumentProxy | null>(null);
  const renderTokenRef = useRef<number>(0);

  // 加载 PDF 文档
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCurrent(1);
    (async () => {
      try {
        const pdfjs = await getPdfjsLib();
        const doc = await pdfjs.getDocument({ url: material.streamUrl }).promise;
        if (cancelled) return;
        docRef.current = doc;
        setTotal(doc.numPages);
        setLoading(false);
      } catch (e) {
        if (cancelled) return;
        if (material.previewReady) {
          setError("幻灯片加载失败，请检查网络或下载到本地查看");
        } else {
          setError("预览尚未生成，请稍后重试或下载到本地查看");
        }
        setLoading(false);
        // eslint-disable-next-line no-console
        console.error("[SlideshowViewer] load failed", e);
      }
    })();
    return () => {
      cancelled = true;
      const doc = docRef.current;
      if (doc) {
        try {
          doc.destroy();
        } catch {
          /* noop */
        }
        docRef.current = null;
      }
    };
  }, [material.streamUrl, material.previewReady]);

  // 渲染当前页到 canvas（按容器宽度自适应）
  const renderCurrent = useCallback(async () => {
    const doc = docRef.current;
    const canvas = canvasRef.current;
    if (!doc || !canvas) return;
    const token = ++renderTokenRef.current;
    try {
      const page = await doc.getPage(current);
      if (token !== renderTokenRef.current) return; // 过时渲染
      // 自适应：基于容器宽度计算 scale
      const containerWidth = canvas.parentElement?.clientWidth ?? 960;
      const baseVp = page.getViewport({ scale: 1 });
      const scale = Math.min(
        2.0,
        Math.max(0.5, (containerWidth - 32) / baseVp.width),
      );
      await renderPageToCanvas(page, canvas, scale);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error("[SlideshowViewer] render failed", e);
    }
  }, [current]);

  useEffect(() => {
    if (total === 0) return;
    renderCurrent();
  }, [renderCurrent, total]);

  // 翻页
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
      } else if (e.key === "Escape") {
        // 全屏时按 Esc 退出，浏览器原生处理
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prev, next]);

  const handleFullscreen = useCallback(() => {
    const el = canvasRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else if (el.requestFullscreen) {
      el.requestFullscreen().catch(() => {});
    }
  }, []);

  // 容器尺寸变化时重渲染
  useEffect(() => {
    const onResize = () => renderCurrent();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [renderCurrent]);

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
        <a
          data-testid="p-viewer-download-link"
          href={material.downloadUrl}
          className="text-sm text-primary-300 hover:underline"
        >
          下载到本地
        </a>
      </header>

      <div
        data-testid="p-viewer-ppt"
        className="flex-1 flex items-center justify-center p-6 min-h-[60vh]"
      >
        {loading && (
          <div className="text-slate-300">正在加载幻灯片…</div>
        )}
        {error && (
          <div className="text-red-300 text-center">
            {error}
            <div className="mt-3">
              <a
                href={material.downloadUrl}
                className="text-sm text-primary-300 hover:underline"
              >
                下载到本地
              </a>
            </div>
          </div>
        )}
        {!loading && !error && (
          <canvas
            ref={canvasRef}
            data-testid="p-viewer-ppt-canvas"
            className="max-w-full max-h-[80vh] bg-white shadow-2xl transition-opacity duration-200"
            style={{ opacity: transitioning ? 0 : 1 }}
          />
        )}
      </div>

      {!loading && !error && total > 0 && (
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
      )}
    </main>
  );
}

export default SlideshowViewer;