import { useCallback, useEffect, useState } from "react";
import { TagAPI } from "@/api";
import { toast } from "@/stores/toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";

export function TagsPage() {
  const [data, setData] = useState<{ items: Array<{ id: number; name: string; coursewareCount: number; createdAt: string | null }>; total: number; page: number; size: number }>({
    items: [],
    total: 0,
    page: 1,
    size: 20,
  });
  const [keyword, setKeyword] = useState("");
  const [name, setName] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [confirmDel, setConfirmDel] = useState<{ id: number; name: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await TagAPI.list({ keyword: keyword || undefined, page: 1, size: 200 });
      setData(resp);
    } catch (e) {
      toast((e as Error).message || "加载失败", "error");
    } finally {
      setLoading(false);
    }
  }, [keyword]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast("请输入标签名", "error");
      return;
    }
    try {
      await TagAPI.create(name.trim());
      setName("");
      toast("已添加", "success");
      reload();
    } catch (e) {
      toast((e as Error).message || "创建失败", "error");
    }
  };

  const submitRename = async (id: number) => {
    if (!editName.trim()) {
      setEditingId(null);
      return;
    }
    try {
      await TagAPI.rename(id, editName.trim());
      toast("已重命名", "success");
      setEditingId(null);
      reload();
    } catch (e) {
      toast((e as Error).message || "重命名失败", "error");
    }
  };

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await TagAPI.remove(confirmDel.id);
      toast("已删除", "success");
      setConfirmDel(null);
      reload();
    } catch (e) {
      toast((e as Error).message || "删除失败", "error");
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <form className="flex gap-2" onSubmit={handleCreate}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            data-testid="new-tag-name"
            placeholder="新标签名"
            maxLength={30}
            className="flex-1 border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            type="submit"
            data-testid="add-tag"
            className="px-4 py-1.5 rounded bg-primary-600 text-white hover:bg-primary-700 text-sm"
          >
            添加
          </button>
        </form>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-base font-semibold flex-1">标签列表</h2>
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            data-testid="tag-search"
            placeholder="搜索标签"
            className="border border-slate-300 rounded px-2 py-1 text-sm w-48"
          />
          <span className="text-xs text-slate-500" data-testid="tag-total">
            共 {data.total} 个
          </span>
        </div>

        {loading ? (
          <div className="text-slate-500 text-sm">加载中…</div>
        ) : data.items.length === 0 ? (
          <div className="text-slate-400 text-sm" data-testid="empty-hint">
            暂无标签
          </div>
        ) : (
          <ul className="divide-y divide-slate-100" data-testid="tag-list">
            {data.items.map((t) => (
              <li
                key={t.id}
                className="py-2 flex items-center gap-2"
                data-testid={`tag-row-${t.id}`}
              >
                {editingId === t.id ? (
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onBlur={() => submitRename(t.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submitRename(t.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    autoFocus
                    maxLength={30}
                    data-testid={`tag-rename-input-${t.id}`}
                    className="flex-1 border border-slate-300 rounded px-2 py-1 text-sm"
                  />
                ) : (
                  <span
                    className="flex-1 text-sm"
                    onDoubleClick={() => {
                      setEditingId(t.id);
                      setEditName(t.name);
                    }}
                  >
                    {t.name}
                    <span className="text-xs text-slate-400 ml-2">
                      关联 {t.coursewareCount} 个课件
                    </span>
                  </span>
                )}
                <button
                  onClick={() => {
                    setEditingId(t.id);
                    setEditName(t.name);
                  }}
                  data-testid={`tag-rename-${t.id}`}
                  className="text-xs text-slate-500 hover:text-slate-800"
                >
                  重命名
                </button>
                <button
                  onClick={() => setConfirmDel({ id: t.id, name: t.name })}
                  data-testid={`tag-delete-${t.id}`}
                  className="text-xs text-rose-500 hover:text-rose-700"
                >
                  删除
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={!!confirmDel}
        title="确认删除"
        message={
          confirmDel
            ? `确定删除标签「${confirmDel.name}」吗?所有引用该标签的课件将自动解绑。`
            : ""
        }
        destructive
        confirmText="删除"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}
