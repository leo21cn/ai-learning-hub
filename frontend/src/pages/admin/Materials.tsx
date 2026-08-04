import { useCallback, useEffect, useRef, useState } from "react";
import { MaterialAPI, type MaterialItem } from "@/api";
import { toast } from "@/stores/toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const TYPE_LABELS: Record<string, string> = { VIDEO: "视频", PDF: "PDF", PPT: "PPT", ZIP: "ZIP文档" };
const MAX_SIZE_BYTES = 500 * 1024 * 1024; // 与后端 MAX_SIZE_BYTES、nginx client_max_body_size 对齐

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

/**
 * 把 axios 抛出的原始错误映射为对用户友好的中文提示。
 * - 413 / MATERIAL_SIZE_EXCEEDED：文件超限
 * - 超时 / 网络中断：网络异常
 * - 其他：保留原始 message 兜底
 */
function friendlyUploadError(e: unknown, fileName: string): string {
  const err = e as {
    code?: string;
    status?: number;
    message?: string;
  };
  if (err.code === "MATERIAL_SIZE_EXCEEDED" || err.status === 413) {
    return `${fileName} 超过 500MB 上限，请压缩或拆分后重试`;
  }
  if (err.status && err.status >= 500) {
    return `${fileName} 上传失败：服务器异常，请稍后重试`;
  }
  if (err.message?.includes("timeout")) {
    return `${fileName} 上传超时，请检查网络后重试`;
  }
  if (err.message?.includes("Network Error")) {
    return `${fileName} 上传失败：网络异常，请检查连接后重试`;
  }
  return `${fileName} 上传失败：${err.message || "未知错误，请稍后重试"}`;
}

export function MaterialsPage() {
  // 分页状态:与 Coursewares 对齐(SIZE=15/页)。
  // 后端 list_paged 已实现 OFFSET/LIMIT + total,前端只需正确传 page/size。
  const [items, setItems] = useState<MaterialItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const SIZE = 15;
  const [keyword, setKeyword] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [confirmDel, setConfirmDel] = useState<MaterialItem | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    try {
      const resp = await MaterialAPI.list({
        keyword: keyword || undefined,
        type: typeFilter || undefined,
        page,
        size: SIZE,
      });
      setItems(resp.items);
      setTotal(resp.total);
    } catch (e) {
      toast((e as Error).message || "加载失败", "error");
    }
  }, [keyword, typeFilter, page]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const f of Array.from(files)) {
        // 预校验:超过 500MB 直接拒绝,不发起请求,避免 nginx 直接 413
        if (f.size > MAX_SIZE_BYTES) {
          toast(
            `${f.name} 超过 500MB 上限，请压缩或拆分后重试`,
            "error",
          );
          continue;
        }
        try {
          await MaterialAPI.upload(f);
          toast(`已上传 ${f.name}`, "success");
        } catch (e) {
          toast(friendlyUploadError(e, f.name), "error");
        }
      }
      reload();
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await MaterialAPI.remove(confirmDel.id);
      toast("已删除", "success");
      setConfirmDel(null);
      reload();
    } catch (e) {
      toast((e as Error).message || "删除失败", "error");
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div
        data-testid="upload-dropzone"
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`bg-white border-2 border-dashed rounded-lg p-6 mb-4 text-center cursor-pointer transition ${
          dragOver ? "border-primary-500 bg-primary-50" : "border-slate-300"
        }`}
        onClick={() => fileRef.current?.click()}
      >
        <p className="text-slate-700 font-medium">
          {uploading ? "上传中…" : "拖拽文件到此处,或点击选择"}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          支持 MP4 / PDF / PPT / PPTX / ZIP,单文件 ≤ 500MB
        </p>
        <input
          ref={fileRef}
          data-testid="upload-file-input"
          type="file"
          multiple
          accept=".mp4,.pdf,.ppt,.pptx,.zip"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-base font-semibold flex-1">素材列表</h2>
          <input
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
            placeholder="搜索名称"
            data-testid="material-search"
            className="border border-slate-300 rounded px-2 py-1 text-sm w-48"
          />
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            data-testid="material-type-filter"
            className="border border-slate-300 rounded px-2 py-1 text-sm"
          >
            <option value="">全部</option>
            <option value="VIDEO">视频</option>
            <option value="PDF">PDF</option>
            <option value="PPT">PPT</option>
            <option value="ZIP">ZIP文档</option>
          </select>
          <span className="text-xs text-slate-500" data-testid="material-total">
            共 {total} 个
          </span>
        </div>

        {items.length === 0 ? (
          <div className="text-slate-400 text-sm" data-testid="empty-hint">
            暂无素材
          </div>
        ) : (
          <table className="w-full text-sm" data-testid="material-table">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-100">
                <th className="py-2 pr-2">名称</th>
                <th className="py-2 pr-2">类型</th>
                <th className="py-2 pr-2">大小</th>
                <th className="py-2 pr-2">上传时间</th>
                <th className="py-2 pr-2">引用</th>
                <th className="py-2 pr-2">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id} className="border-b border-slate-100" data-testid={`material-row-${m.id}`}>
                  <td className="py-2 pr-2 font-medium text-slate-800">{m.name}</td>
                  <td className="py-2 pr-2">
                    <span className="px-2 py-0.5 rounded bg-slate-100 text-xs">
                      {TYPE_LABELS[m.type] || m.type}
                    </span>
                  </td>
                  <td className="py-2 pr-2 text-slate-500">{formatBytes(m.sizeBytes)}</td>
                  <td className="py-2 pr-2 text-slate-500">
                    {m.uploadedAt ? new Date(m.uploadedAt).toLocaleString() : "-"}
                  </td>
                  <td className="py-2 pr-2 text-slate-500">{m.referenced ? "是" : "否"}</td>
                  <td className="py-2 pr-2 space-x-2">
                    <a
                      href={MaterialAPI.fileUrl(m.id)}
                      data-testid={`material-download-${m.id}`}
                      className="text-xs text-primary-600 hover:text-primary-800"
                    >
                      下载
                    </a>
                    <button
                      onClick={() => setConfirmDel(m)}
                      data-testid={`material-delete-${m.id}`}
                      disabled={m.referenced}
                      className="text-xs text-rose-500 hover:text-rose-700 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* 分页:与 Coursewares.tsx 一致风格;仅当总条数超 1 页时显示 */}
        {total > SIZE && (
          <div className="mt-4 flex justify-center items-center gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              data-testid="material-prev-page"
              className="px-3 py-1 border border-slate-300 rounded disabled:opacity-40 hover:bg-slate-50"
            >
              上一页
            </button>
            <span
              className="px-3 py-1 text-slate-600 text-sm"
              data-testid="material-pager-info"
            >
              第 {page} 页 / 共 {Math.ceil(total / SIZE)} 页
            </span>
            <button
              disabled={page * SIZE >= total}
              onClick={() => setPage((p) => p + 1)}
              data-testid="material-next-page"
              className="px-3 py-1 border border-slate-300 rounded disabled:opacity-40 hover:bg-slate-50"
            >
              下一页
            </button>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!confirmDel}
        title="确认删除"
        message={confirmDel ? `确定删除素材「${confirmDel.name}」吗?` : ""}
        destructive
        confirmText="删除"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}
