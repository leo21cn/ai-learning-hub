/** 视频播放子组件：简化版流媒体样式。
 *
 * - 左侧主播放区（深色背景）
 * - 右侧 280px 信息面板（类型/时长/大小/下载）
 * - 标准 HTML5 video controls
 */
import { useEffect, useRef } from "react";
import type { PublicMaterialItem } from "@/api";

type Props = {
  material: PublicMaterialItem;
  onBack: () => void;
  onLogo: () => void;
};

function formatSize(bytes: number): string {
  if (!bytes) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function VideoPlayer({ material, onBack, onLogo }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // 自动隐藏光标：播放时 2 秒无操作隐藏
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    let timer: number | null = null;
    const hide = () => {
      if (v.parentElement) v.parentElement.style.cursor = "none";
    };
    const show = () => {
      if (v.parentElement) v.parentElement.style.cursor = "";
    };
    const reset = () => {
      show();
      if (timer != null) window.clearTimeout(timer);
      timer = window.setTimeout(hide, 2000);
    };
    const onPlay = () => reset();
    const onPause = () => {
      show();
      if (timer != null) window.clearTimeout(timer);
    };
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    v.addEventListener("mousemove", reset);
    return () => {
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onPause);
      v.removeEventListener("mousemove", reset);
      if (timer != null) window.clearTimeout(timer);
    };
  }, []);

  return (
    <main
      data-testid="p-viewer-video-root"
      className="min-h-screen flex flex-col bg-slate-50"
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
          视频
        </span>
        <a
          data-testid="p-viewer-download-link"
          href={material.downloadUrl}
          className="text-sm text-primary-600 hover:underline"
        >
          下载到本地
        </a>
      </header>

      <div className="flex-1 grid gap-4 p-4 md:grid-cols-[1fr_280px]">
        <div className="bg-black rounded-lg flex items-center justify-center min-h-[300px]">
          <video
            ref={videoRef}
            data-testid="p-viewer-video"
            controls
            preload="metadata"
            className="w-full max-h-[80vh]"
            src={material.streamUrl}
          >
            您的浏览器不支持 HTML5 视频播放，请
            <a href={material.downloadUrl}>下载到本地</a>查看。
          </video>
        </div>

        <aside
          data-testid="p-viewer-video-info"
          className="bg-white rounded-lg border border-slate-200 p-4 space-y-3 text-sm"
        >
          <h3
            data-testid="p-viewer-video-info-name"
            className="text-base font-medium text-slate-900 break-all"
          >
            {material.name}
          </h3>
          <dl className="space-y-2 text-slate-700">
            <div className="flex justify-between gap-3">
              <dt>类型</dt>
              <dd>视频</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>时长</dt>
              <dd>{material.duration ?? "--"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>大小</dt>
              <dd>{formatSize(material.sizeBytes)}</dd>
            </div>
          </dl>
          <a
            href={material.downloadUrl}
            className="inline-flex items-center text-sm text-primary-600 hover:underline"
          >
            下载到本地
          </a>
        </aside>
      </div>
    </main>
  );
}

export default VideoPlayer;