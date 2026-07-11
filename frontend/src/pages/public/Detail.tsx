/**
 * P-DETAIL:课件详情。
 *
 * 通过 ?id=<coursewareId> 调用 /api/public/coursewares/{id};RESTRICTED
 * 课件需要客户端已记忆 tokenHash,并以 X-Token-Hash 头传入;否则由前
 * 端拦截跳回 P-LOCKED。
 *
 * v1.2 起:P-DETAIL 不再提供任何"下载到本地"入口,仅保留"在线浏览"按钮。
 * 后端 `/api/public/materials/{id}/file` 端点仍存在,仅供管理后台 / 调试。
 *
 * v1.5 起:素材列表按管理员设定的 sortOrder 升序展示。
 */
import { useEffect, useMemo, useState } from "react";
import { useViewStore } from "@/stores/view";
import { PublicCoursewareAPI, type CoursewareItem } from "@/api";

export function DetailPage() {
  const id = useViewStore((s) => s.id);
  const go = useViewStore((s) => s.go);
  const [cw, setCw] = useState<CoursewareItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (id == null) {
      go({ view: "home" });
      return;
    }
    let cancel = false;
    setLoading(true);
    setErr(null);
    // 走封装的 API;RESTRICTED 课件如果尚未记忆 tokenHash,服务端返回 403,
    // 这里捕到后切回 P-LOCKED 让用户输入。
    // 注意:apiClient 请求拦截器会自动从 useTokenStore 读 tokenHash 并加
    // X-Token-Hash 头,即使 cookie 还未写入也能解锁。
    PublicCoursewareAPI.get(id as number)
      .then((cw) => {
        if (cancel) return;
        setCw(cw);
      })
      .catch((e: unknown) => {
        if (cancel) return;
        const err = e as Error & { status?: number; code?: string };
        if (err.status === 403 || err.code === "courseware_locked") {
          go({ view: "locked", id });
        } else {
          setErr(err.message || "加载失败");
        }
      })
      .finally(() => !cancel && setLoading(false));
    return () => {
      cancel = true;
    };
  }, [id, go]);

  const handleBrowse = (materialId: number) => {
    // 跳转到 P-VIEWER,根据素材类型渲染三种样式
    go({ view: "viewer", id: materialId, coursewareId: id });
  };

  const breadcrumb = useMemo(() => {
    if (!cw) return "";
    return cw.categoryName || "";
  }, [cw]);

  if (id == null) return null;

  return (
    <main className="max-w-4xl mx-auto py-10 px-4" data-testid="page-detail">
      <button
        onClick={() => go({ view: "home" })}
        className="text-sm text-slate-500 hover:underline mb-4"
      >
        ← 返回首页
      </button>

      {loading && (
        <div className="text-center text-slate-500 py-12">加载中…</div>
      )}
      {err && (
        <div className="text-center text-rose-600 py-12" data-testid="detail-err">
          {err}
        </div>
      )}

      {cw && (
        <article>
          <header className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              {breadcrumb && (
                <span className="text-xs text-slate-500">{breadcrumb}</span>
              )}
              <span
                className={`px-2 py-0.5 text-xs rounded ${
                  cw.accessMode === "RESTRICTED"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-emerald-100 text-emerald-700"
                }`}
              >
                {cw.accessMode === "RESTRICTED" ? "受限" : "开放"}
              </span>
            </div>
            <h1
              className="text-3xl font-bold text-slate-800"
              data-testid="detail-title"
            >
              {cw.title}
            </h1>
            {cw.author && (
              <p className="text-sm text-slate-500 mt-2">作者: {cw.author}</p>
            )}
            {cw.tagNames?.length > 0 && (
              <div className="mt-2 flex gap-1 flex-wrap">
                {cw.tagNames.map((t, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-600"
                  >
                    #{t}
                  </span>
                ))}
              </div>
            )}
          </header>

          {cw.description && (
            <section className="bg-white border border-slate-200 rounded-lg p-5 mb-6">
              <h2 className="text-sm font-semibold text-slate-700 mb-2">简介</h2>
              <p className="text-slate-700 whitespace-pre-wrap">
                {cw.description}
              </p>
            </section>
          )}

          <section>
            <h2 className="text-sm font-semibold text-slate-700 mb-3">
              素材文件({cw.materials?.length ?? 0})
            </h2>
            <ul className="space-y-2" data-testid="detail-materials">
              {cw.materials?.length === 0 && (
                <li className="text-sm text-slate-400">该课件尚未上传素材</li>
              )}
              {cw.materials?.map((m) => {
                // ZIP 走下载，其他可浏览类型进入 P-VIEWER；未知类型默认为下载兜底。
                const isBrowsable =
                  m.type === "VIDEO" || m.type === "PDF" || m.type === "PPT";
                return (
                  <li
                    key={m.id}
                    data-testid="p-detail-material"
                    data-material-type={m.type}
                    data-material-id={m.id}
                    className="bg-white border border-slate-200 rounded p-3 flex items-center justify-between gap-3"
                  >
                    <div className="text-sm min-w-0 flex-1">
                      <span className="font-medium text-slate-800 break-all">
                        {m.name}
                      </span>
                      <span className="text-xs text-slate-500 ml-2 whitespace-nowrap">
                        ({m.type}, {Math.round(m.sizeBytes / 1024)} KB)
                      </span>
                    </div>
                    {/* v1.2 起 P-DETAIL 不再提供“下载到本地”入口；ZIP/未知类型作为例外仅提供下载。 */}
                    <div className="flex items-center gap-2 shrink-0">
                      {isBrowsable ? (
                        <button
                          data-testid="p-detail-material-browse-btn"
                          onClick={() => handleBrowse(m.id)}
                          className="text-sm text-primary-600 hover:bg-primary-50 px-3 py-1 rounded"
                        >
                          在线浏览
                        </button>
                      ) : (
                        <a
                          href={m.downloadUrl}
                          download={m.name}
                          data-testid="p-detail-material-download-btn"
                          className="text-sm text-primary-600 hover:bg-primary-50 px-3 py-1 rounded"
                        >
                          下载
                        </a>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        </article>
      )}
    </main>
  );
}
