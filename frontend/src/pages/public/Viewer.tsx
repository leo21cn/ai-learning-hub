/** 素材在线浏览页 P-VIEWER：根据素材类型分发到三个子组件。
 *
 * - VIDEO → VideoPlayer
 * - PDF → PdfReader（类似 Word 阅读样式）
 * - PPT → SlideshowViewer（幻灯片样式）
 *
 * P-VIEWER 范围：从 API 拿到的 material 对象不再透传 `downloadUrl` 给子组件，
 * 避免子组件误引用导致下载入口泄露。`streamUrl` / `imageUrls` 等仍按需透传。
 */
import { useEffect, useState } from "react";
import { PublicCoursewareAPI, type PublicMaterialItem } from "@/api";
import { useViewStore } from "@/stores/view";
import { VideoPlayer } from "./viewer/VideoPlayer";
import { PdfReader } from "./viewer/PdfReader";
import { SlideshowViewer } from "./viewer/SlideshowViewer";

function ViewerError({ message, onBack }: { message: string; onBack: () => void }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 text-slate-700 p-8">
      <div className="bg-white rounded-lg border border-slate-200 p-8 max-w-md text-center space-y-4">
        <h2 className="text-lg font-medium text-slate-900">预览加载失败</h2>
        <p className="text-sm">{message}</p>
        <button
          type="button"
          onClick={onBack}
          className="px-4 py-2 rounded bg-primary-600 text-white hover:bg-primary-700 text-sm"
        >
          ← 返回详情
        </button>
      </div>
    </div>
  );
}

export function Viewer() {
  const id = useViewStore((s) => s.id);
  const coursewareId = useViewStore((s) => s.coursewareId);
  const go = useViewStore((s) => s.go);
  const [material, setMaterial] = useState<PublicMaterialItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id == null) {
      setError("缺少素材参数");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    PublicCoursewareAPI.getMaterial(id)
      .then((data) => {
        if (cancelled) return;
        setMaterial(data);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg =
          (e as { message?: string })?.message ?? "素材加载失败，请稍后重试";
        setError(msg);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // 返回 P-DETAIL：携带 coursewareId 时回到课件详情；否则回到首页（plan §5a.6）。
  const handleBack = () => {
    if (coursewareId != null) {
      go({ view: "detail", id: coursewareId, coursewareId: null });
    } else {
      go({ view: "home", id: null, coursewareId: null });
    }
  };

  // Logo 永远回 P-HOME（plan §5a.6）。
  const handleLogo = () => {
    go({ view: "home", id: null, coursewareId: null });
  };

  if (loading) {
    return (
      <div
        data-testid="p-viewer-loading"
        className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-500"
      >
        正在加载预览…
      </div>
    );
  }

  if (error || !material) {
    return <ViewerError message={error ?? "素材不存在"} onBack={handleBack} />;
  }

  // P-VIEWER 屏蔽下载：从透传给子组件的 material 中剥离 downloadUrl。
  // 保留其他字段(streamUrl / imageUrls / sizeBytes / duration / previewReady …)。
  const { downloadUrl: _ignored, ...viewerMaterial } = material;
  void _ignored;

  switch (material.type) {
    case "VIDEO":
      return (
        <VideoPlayer material={viewerMaterial} onBack={handleBack} onLogo={handleLogo} />
      );
    case "PDF":
      return (
        <PdfReader material={viewerMaterial} onBack={handleBack} onLogo={handleLogo} />
      );
    case "PPT":
      return (
        <SlideshowViewer
          material={viewerMaterial}
          onBack={handleBack}
          onLogo={handleLogo}
        />
      );
    default:
      return (
        <ViewerError
          message={`不支持的素材类型：${material.type}`}
          onBack={handleBack}
        />
      );
  }
}

export default Viewer;