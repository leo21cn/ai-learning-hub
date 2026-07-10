/** PDF 阅读子组件：类似 Word 阅读样式。
 *
 * - 顶部工具条（缩放 −/+ / 当前比例 / 返回）
 * - 主体居中 max-w-[820px] 连续滚动
 * - 右下角圆角页码气泡 `第 N / M 页`
 * - 双击页面放大 / 还原
 *
 * P-VIEWER 范围：禁止任何"下载到本地"入口。`material.downloadUrl` 不再被引用。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PublicMaterialItem } from "@/api";
import { getPdfjsLib, renderPageToCanvas } from "@/lib/pdfjs";

type Props = {
  material: PublicMaterialItem;
  onBack: () => void;
  onLogo: () => void;
};

const SCALE_PRESETS = [0.75, 1.0, 1.25, 1.5, 2.0];
// R-Viewer-PDF-1:PDF 默认按原始尺寸(100%)渲染,单页页面以其 canvas 实际宽度
// 水平居中;窄屏时允许横向滚动查看完整内容。
const DEFAULT_SCALE = 1.0;

export function PdfReader({ material, onBack, onLogo }: Props) {
  const [scale, setScale] = useState<number>(DEFAULT_SCALE);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const docRef = useRef<import("pdfjs-dist").PDFDocumentProxy | null>(null);
  const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());

  // 加载 PDF 文档
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const pdfjs = await getPdfjsLib();
        const doc = await pdfjs.getDocument({ url: material.streamUrl }).promise;
        if (cancelled) return;
        docRef.current = doc;
        setTotalPages(doc.numPages);
        setLoading(false);
      } catch (e) {
        if (cancelled) return;
        const err = e as Error & { name?: string; message?: string };
        // 上报详细错误到控制台,便于排查 worker 加载失败 vs PDF 本身损坏 vs 权限 403
        // eslint-disable-next-line no-console
        console.error("[PdfReader] load failed", {
          name: err?.name,
          message: err?.message,
          stack: err?.stack,
          streamUrl: material.streamUrl,
        });
        const reason =
          err?.name === "PasswordException"
            ? "PDF 受密码保护"
            : err?.message?.includes("401") || err?.message?.includes("403")
              ? "未授权访问该素材"
              : "PDF 加载失败，请检查网络后刷新重试";
        setError(reason);
        setLoading(false);
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
  }, [material.streamUrl]);

  // 渲染所有页到 canvas（scale 变化时重渲染）
  useEffect(() => {
    const doc = docRef.current;
    if (!doc || totalPages === 0) return;
    let cancelled = false;
    (async () => {
      for (let i = 1; i <= totalPages; i++) {
        if (cancelled) return;
        const page = await doc.getPage(i);
        const canvas = canvasRefs.current.get(i);
        if (!canvas) continue;
        try {
          await renderPageToCanvas(page, canvas, scale);
        } catch (e) {
          // 单页失败不阻塞整体
          // eslint-disable-next-line no-console
          console.error("[PdfReader] render page", i, "failed", e);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scale, totalPages]);

  // 滚动驱动：IntersectionObserver 监听各页可见性
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const targets: Element[] = Array.from(
      root.querySelectorAll<HTMLDivElement>("[data-page-number]"),
    );
    if (targets.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        // 取最靠近视口中心的可见页
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible.length > 0) {
          const num = Number(
            (visible[0].target as HTMLElement).dataset.pageNumber,
          );
          if (!Number.isNaN(num)) setCurrentPage(num);
        }
      },
      { rootMargin: "0px 0px -50% 0px", threshold: [0.1, 0.5, 0.9] },
    );
    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, [totalPages]);

  const setCanvasRef = useCallback(
    (page: number) => (el: HTMLCanvasElement | null) => {
      if (el) canvasRefs.current.set(page, el);
      else canvasRefs.current.delete(page);
    },
    [],
  );

  const handleZoom = useCallback(
    (dir: 1 | -1) => {
      const idx = SCALE_PRESETS.findIndex((s) => s === scale);
      const next = SCALE_PRESETS[idx + dir];
      if (next != null) setScale(next);
    },
    [scale],
  );

  const handleDoubleClick = useCallback(() => {
    setScale((s) => (s >= 1.5 ? 1.0 : Math.min(2.0, s + 0.25)));
  }, []);

  const zoomLabel = useMemo(() => `${Math.round(scale * 100)}%`, [scale]);

  return (
    <main
      data-testid="p-viewer-pdf-root"
      className="min-h-screen flex flex-col bg-slate-100"
    >
      <header className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 bg-white shadow-sm">
        <button
          type="button"
          data-testid="p-viewer-logo"
          onClick={onLogo}
          aria-label="返回首页"
          className="text-sm font-semibold text-primary-700 hover:bg-slate-100 px-3 py-1 rounded shrink-0"
        >
          🏠 首页
        </button>
        <button
          type="button"
          data-testid="p-viewer-back-btn"
          onClick={onBack}
          className="text-sm text-slate-700 hover:bg-slate-100 px-3 py-1 rounded"
        >
          ← 返回
        </button>
        <h1
          data-testid="p-viewer-title"
          className="text-base font-medium text-slate-900 truncate flex-1"
        >
          {material.name}
        </h1>
        <span className="text-xs px-2 py-0.5 rounded bg-slate-200 text-slate-700">
          PDF
        </span>
      </header>

      <div
        data-testid="p-viewer-pdf-toolbar"
        className="sticky top-[57px] z-10 flex items-center gap-2 px-4 py-2 bg-white border-b border-slate-200 text-sm"
      >
        <button
          type="button"
          data-testid="p-viewer-pdf-zoom-out"
          onClick={() => handleZoom(-1)}
          disabled={scale === SCALE_PRESETS[0]}
          className="px-3 py-1 rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-40"
        >
          −
        </button>
        <button
          type="button"
          data-testid="p-viewer-pdf-zoom-in"
          onClick={() => handleZoom(1)}
          disabled={scale === SCALE_PRESETS[SCALE_PRESETS.length - 1]}
          className="px-3 py-1 rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-40"
        >
          +
        </button>
        <span
          data-testid="p-viewer-pdf-zoom-label"
          className="px-2 text-slate-700 tabular-nums"
        >
          {zoomLabel}
        </span>
      </div>

      <div
        ref={containerRef}
        data-testid="p-viewer-pdf"
        className="flex-1 py-6 px-4"
        onDoubleClick={handleDoubleClick}
      >
        {loading && (
          <div className="text-center text-slate-500 py-12">
            正在加载 PDF…
          </div>
        )}
        {error && (
          <div
            data-testid="p-viewer-pdf-error"
            className="text-center text-red-600 py-12"
          >
            {error}
          </div>
        )}
        {!loading && !error && (
          <div className="flex flex-col items-center gap-4 px-4">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <div
                key={page}
                data-page-number={page}
                className="inline-block bg-white shadow-md"
              >
                <canvas ref={setCanvasRef(page)} />
              </div>
            ))}
          </div>
        )}
      </div>

      {totalPages > 0 && !loading && !error && (
        <div
          data-testid="p-viewer-pdf-page-indicator"
          aria-live="polite"
          className="fixed bottom-4 right-4 px-3 py-1 rounded-full bg-slate-800/80 text-white text-sm shadow"
        >
          第 {currentPage} / {totalPages} 页
        </div>
      )}
    </main>
  );
}

export default PdfReader;