/** 视频播放子组件：简化版流媒体样式。
 *
 * - 左侧主播放区（深色背景）
 * - 右侧 280px 信息面板（类型/时长/大小）
 * - 标准 HTML5 video controls
 *
 * P-VIEWER 范围：禁止任何"下载到本地"入口。`material.downloadUrl` 不再被引用；
 * 关闭 video 上的右键菜单 / contextmenu。
 */
import { useEffect, useRef, useState } from "react";
import type { PublicMaterialItem } from "@/api";

/**
 * 占位最小展示时长：防止 loadeddata / canplay 触发过快导致占位一闪而过
 * (特别是本地缓存命中时 metadata 可能 < 50ms 就可播放)。
 */
const POSTER_MIN_MS = 350;

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
  // ready=true => 首帧已可见,隐藏占位
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 路由切换/换素材时重置
  useEffect(() => {
    setReady(false);
    setError(null);
  }, [material.id]);

  /**
   * 当 onLoadedData / onCanPlay / onPlaying 任一事件触发时,记录最早的时间戳。
   * 只有在 POSTER_MIN_MS 过后才允许 ready=true,避免“占位一闪而过”。
   * (loadedmetadata 只是时长/尺寸等头部元数据,不能保证第一帧已下载——
   * 用它触发会过早隐藏占位,用户反而看到黑屏。)
   */
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    let triggeredAt: number | null = null;
    let timer: number | null = null;
    const tryReady = () => {
      if (ready) return;
      const now = performance.now();
      if (triggeredAt == null) triggeredAt = now;
      const elapsed = now - triggeredAt;
      const remain = POSTER_MIN_MS - elapsed;
      if (remain <= 0) {
        setReady(true);
      } else {
        if (timer != null) window.clearTimeout(timer);
        timer = window.setTimeout(() => setReady(true), remain);
      }
    };
    // 边界：视频可能已缓存(readyState >= 2 表示已有第一帧数据),事件不会重发,直接触发
    if (v.readyState >= 2) {
      tryReady();
      return;
    }
    // 1) loadeddata: 第一帧数据可用,video 会渲染第一帧图(最能代表“首帧可见”)
    v.addEventListener("loadeddata", tryReady);
    // 2) canplay: 缓冲足够可以开始播放(双保险,loadeddata 在某些浏览器上可能不触发)
    v.addEventListener("canplay", tryReady);
    return () => {
      v.removeEventListener("loadeddata", tryReady);
      v.removeEventListener("canplay", tryReady);
      if (timer != null) window.clearTimeout(timer);
    };
  }, [material.id, ready]);

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
      </header>

      <div className="flex-1 grid gap-4 p-4 md:grid-cols-[1fr_280px]">
        <div className="relative bg-black rounded-lg flex items-center justify-center min-h-[300px] overflow-hidden">
          {/* 加载占位(方案 A):首帧出现前遮住黑屏,加载完成后 fade-out 250ms */}
          {!ready && (
            <div
              data-testid="p-viewer-video-poster"
              className={`absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none transition-opacity duration-300 ${
                error
                  ? "bg-gradient-to-br from-rose-900 via-rose-950 to-black"
                  : "bg-gradient-to-br from-slate-800 via-slate-900 to-black"
              } ${ready ? "opacity-0" : "opacity-100"}`}
            >
              <div
                className={`w-20 h-20 rounded-full flex items-center justify-center mb-4 ${
                  error ? "bg-rose-500/20" : "bg-white/10 backdrop-blur"
                } ${error ? "" : "animate-pulse"}`}
              >
                <svg
                  className={`w-10 h-10 ${
                    error ? "text-rose-300" : "text-white/80"
                  }`}
                  fill="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden
                >
                  {error ? (
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
                  ) : (
                    <path d="M8 5v14l11-7z" />
                  )}
                </svg>
              </div>
              <p
                className={`text-sm ${
                  error ? "text-rose-200" : "text-white/70"
                }`}
                data-testid="p-viewer-video-poster-msg"
              >
                {error ?? "视频加载中…"}
              </p>
              {!error && (
                <p
                  className="text-white/40 text-xs mt-2 max-w-xs text-center px-4 truncate"
                  data-testid="p-viewer-video-poster-name"
                >
                  {material.name}
                </p>
              )}
            </div>
          )}
          <video
            ref={videoRef}
            data-testid="p-viewer-video"
            controls
            controlsList="nodownload"
            disablePictureInPicture
            onContextMenu={(e) => e.preventDefault()}
            preload="auto"
            className="w-full max-h-[80vh] select-none"
            src={material.streamUrl}
            onError={() => setError("视频加载失败，请检查网络")}
          >
            您的浏览器不支持 HTML5 视频播放，请使用现代浏览器查看。
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
              <dd data-testid="p-viewer-video-duration">
                {material.duration ?? "--"}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>大小</dt>
              <dd>{formatSize(material.sizeBytes)}</dd>
            </div>
          </dl>
        </aside>
      </div>
    </main>
  );
}

export default VideoPlayer;