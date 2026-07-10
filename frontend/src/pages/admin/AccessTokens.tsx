import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AccessTokenAPI,
  type AccessTokenCreated,
  type AccessTokenItem,
} from "@/api";
import { toast } from "@/stores/toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";

export function AccessTokensPage() {
  const [items, setItems] = useState<AccessTokenItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [confirmDel, setConfirmDel] = useState<AccessTokenItem | null>(null);
  const [created, setCreated] = useState<AccessTokenCreated | null>(null);
  const [confirmRegen, setConfirmRegen] = useState<AccessTokenItem | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await AccessTokenAPI.list({ size: 200 });
      setItems(data.items);
    } catch (e) {
      toast((e as Error).message || "加载失败", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleCreate = async () => {
    const label = newLabel.trim();
    if (!label) {
      toast("请填写标签", "error");
      return;
    }
    try {
      const res = await AccessTokenAPI.create(label);
      setCreated(res);
      setNewLabel("");
      toast("已创建", "success");
      reload();
    } catch (e) {
      toast((e as Error).message || "创建失败", "error");
    }
  };

  const handleRegenerate = async () => {
    if (!confirmRegen) return;
    try {
      const res = await AccessTokenAPI.regenerate(confirmRegen.id);
      setCreated(res);
      toast("已重新生成", "success");
      reload();
    } catch (e) {
      toast((e as Error).message || "重新生成失败", "error");
    } finally {
      setConfirmRegen(null);
    }
  };

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await AccessTokenAPI.remove(confirmDel.id);
      toast("已删除", "success");
      reload();
    } catch (e) {
      toast((e as Error).message || "删除失败", "error");
    } finally {
      setConfirmDel(null);
    }
  };

  const filtered = items.filter((t) =>
    keyword ? t.label.toLowerCase().includes(keyword.toLowerCase()) : true,
  );

  return (
    <div className="max-w-5xl mx-auto">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">访问令牌管理</h1>
          <p className="text-sm text-slate-500 mt-1">
            仅管理员可见;令牌明文仅在创建/重新生成时一次性返回
          </p>
        </div>
      </header>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4 mb-4">
        <div className="flex gap-2">
          <input
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            data-testid="token-new-label"
            placeholder="新令牌标签(全局唯一)"
            className="flex-1 border border-slate-300 rounded-md px-3 py-2"
          />
          <button
            onClick={handleCreate}
            data-testid="token-create-btn"
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md"
          >
            生成令牌
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 mb-4 p-4">
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索标签"
          className="w-full border border-slate-300 rounded-md px-3 py-2"
        />
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-left">
            <tr>
              <th className="px-4 py-2">ID</th>
              <th className="px-4 py-2">标签</th>
              <th className="px-4 py-2">引用课件数</th>
              <th className="px-4 py-2">创建时间</th>
              <th className="px-4 py-2">最近重新生成</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  加载中...
                </td>
              </tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  暂无数据
                </td>
              </tr>
            )}
            {!loading &&
              filtered.map((t) => (
                <tr
                  key={t.id}
                  data-testid={`token-row-${t.id}`}
                  className="border-t border-slate-100 hover:bg-slate-50"
                >
                  <td className="px-4 py-2 text-slate-700">{t.id}</td>
                  <td className="px-4 py-2 font-medium text-slate-800">
                    {t.label}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {t.coursewareCount}
                  </td>
                  <td className="px-4 py-2 text-slate-500 text-xs">
                    {t.createdAt ? new Date(t.createdAt).toLocaleString() : "-"}
                  </td>
                  <td className="px-4 py-2 text-slate-500 text-xs">
                    {t.regeneratedAt
                      ? new Date(t.regeneratedAt).toLocaleString()
                      : "-"}
                  </td>
                  <td className="px-4 py-2 text-right space-x-2">
                    <Link
                      to={`/admin/access-tokens/${t.id}/usage`}
                      data-testid={`token-usage-${t.id}`}
                      className="px-2 py-1 text-primary-600 hover:bg-primary-50 rounded inline-block"
                    >
                      访问记录
                    </Link>
                    <button
                      onClick={() => setConfirmRegen(t)}
                      data-testid={`token-regen-${t.id}`}
                      className="px-2 py-1 text-amber-600 hover:bg-amber-50 rounded"
                    >
                      重新生成
                    </button>
                    <button
                      onClick={() => setConfirmDel(t)}
                      data-testid={`token-del-${t.id}`}
                      className="px-2 py-1 text-rose-600 hover:bg-rose-50 rounded"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {created && (
        <div
          className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50"
          data-testid="token-created-modal"
        >
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-bold text-amber-700 mb-2">
              请妥善保存此令牌
            </h3>
            <p className="text-sm text-slate-600 mb-4">
              此明文仅显示一次,请立即复制并妥善保存。
            </p>
            <div className="bg-slate-100 rounded p-3 font-mono text-sm break-all mb-4">
              {created.value}
            </div>
            <div className="text-xs text-slate-500 mb-4">
              标签: {created.label} · 哈希: {created.valueHash.slice(0, 16)}...
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(created.value);
                  toast("已复制到剪贴板", "success");
                }}
                className="px-3 py-1.5 border border-slate-300 rounded hover:bg-slate-50"
              >
                复制
              </button>
              <button
                onClick={() => setCreated(null)}
                className="px-3 py-1.5 bg-primary-600 text-white rounded hover:bg-primary-700"
              >
                我已保存
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmRegen !== null}
        title="重新生成令牌"
        message={
          confirmRegen
            ? `重新生成 "${confirmRegen.label}" 会立即作废旧明文,确认继续?`
            : ""
        }
        confirmText="重新生成"
        tone="warning"
        onConfirm={handleRegenerate}
        onCancel={() => setConfirmRegen(null)}
      />
      <ConfirmDialog
        open={confirmDel !== null}
        title="删除令牌"
        message={
          confirmDel
            ? `确认删除 "${confirmDel.label}"?如有课件引用将无法删除。`
            : ""
        }
        confirmText="删除"
        tone="danger"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}
