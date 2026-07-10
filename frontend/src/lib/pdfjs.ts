/**
 * PDF.js 单例封装：懒加载、worker 路径统一。
 *
 * 使用方式：
 *   import { getPdfjsLib } from "@/lib/pdfjs";
 *   const pdfjs = await getPdfjsLib();
 *   const doc = await pdfjs.getDocument(url).promise;
 *
 * worker 路径规则：
 *   - 生产构建：`/pdf.worker.min.mjs` 由 vite 插件 / Dockerfile 复制到 dist 根目录
 *   - 开发模式：`?url` 拿到 vite dev 服务动态 URL
 */
import * as pdfjsLib from "pdfjs-dist";
import devWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

let configured = false;

export async function getPdfjsLib(): Promise<typeof pdfjsLib> {
  if (!configured) {
    // 生产：固定路径 /pdf.worker.min.mjs（由 vite 插件或 Dockerfile 复制到 dist 根）
    // 开发：使用 vite dev server 动态 URL
    // 末尾加 ?v=20260709 强制 cache-bust——修复后 504 OK 之前可能缓存了 404，浏览器不一定主动重试
    const workerBase = import.meta.env.PROD
      ? "/pdf.worker.min.mjs"
      : (devWorkerUrl as string);
    pdfjsLib.GlobalWorkerOptions.workerSrc = `${workerBase}?v=20260709`;
    configured = true;
  }
  return pdfjsLib;
}

export type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";

export const PDFJS_VERSION = pdfjsLib.version ?? "4.7.x";

/**
 * 渲染 PDF 单页到 canvas 的辅助函数：根据设备像素比做高 DPI 适配。
 */
export async function renderPageToCanvas(
  page: import("pdfjs-dist").PDFPageProxy,
  canvas: HTMLCanvasElement,
  scale = 1.25,
): Promise<void> {
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const viewport = page.getViewport({ scale: scale * dpr });
  canvas.width = Math.floor(viewport.width);
  canvas.height = Math.floor(viewport.height);
  canvas.style.width = `${Math.floor(viewport.width / dpr)}px`;
  canvas.style.height = `${Math.floor(viewport.height / dpr)}px`;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  // 每次 render 前清理避免残留
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  await page.render({ canvasContext: ctx, viewport }).promise;
}

export default pdfjsLib;