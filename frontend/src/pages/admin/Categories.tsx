import { useCallback, useEffect, useState } from "react";
import { CategoryAPI, type CategoryNode } from "@/api";
import { toast } from "@/stores/toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";

function flatten(nodes: CategoryNode[], depth = 0, acc: Array<{ node: CategoryNode; depth: number }> = []) {
  for (const n of nodes) {
    acc.push({ node: n, depth });
    flatten(n.children, depth + 1, acc);
  }
  return acc;
}

export function CategoriesPage() {
  const [tree, setTree] = useState<CategoryNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState<Record<number | "root", string>>({ root: "" });
  const [confirmDel, setConfirmDel] = useState<CategoryNode | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await CategoryAPI.list();
      setTree(data);
    } catch (e) {
      toast((e as Error).message || "加载失败", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleCreate = async (
    parentId: number | null,
    nameArg?: string,
  ) => {
    const key = parentId ?? "root";
    // 优先级:显式参数 > state[name] > 空(向后兼容 root 创建入口)
    const name = (nameArg ?? newName[key] ?? "").trim();
    if (!name) {
      toast("请输入分类名称", "error");
      return;
    }
    try {
      await CategoryAPI.create(name, parentId ?? undefined);
      setNewName((m) => ({ ...m, [key]: "" }));
      toast("已添加", "success");
      reload();
    } catch (e) {
      toast((e as Error).message || "创建失败", "error");
    }
  };

  const handleRename = async (id: number, name: string) => {
    try {
      await CategoryAPI.rename(id, name);
      toast("已重命名", "success");
      reload();
    } catch (e) {
      toast((e as Error).message || "重命名失败", "error");
    }
  };

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await CategoryAPI.remove(confirmDel.id);
      toast("已删除", "success");
      setConfirmDel(null);
      reload();
    } catch (e) {
      toast((e as Error).message || "删除失败", "error");
    }
  };

  const rows = flatten(tree);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <h2 className="text-base font-semibold mb-3">新建根分类</h2>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            handleCreate(null);
          }}
        >
          <input
            value={newName.root}
            onChange={(e) => setNewName((m) => ({ ...m, root: e.target.value }))}
            data-testid="new-root-name"
            placeholder="例如:项目运营"
            maxLength={30}
            className="flex-1 border border-slate-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            type="submit"
            data-testid="add-root"
            className="px-4 py-1.5 rounded bg-primary-600 text-white hover:bg-primary-700 text-sm"
          >
            添加
          </button>
        </form>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h2 className="text-base font-semibold mb-3">分类树(最多 3 层)</h2>
        {loading ? (
          <div className="text-slate-500 text-sm">加载中…</div>
        ) : rows.length === 0 ? (
          <div className="text-slate-400 text-sm" data-testid="empty-hint">
            暂无分类,先在顶部添加一个根分类
          </div>
        ) : (
          <ul className="divide-y divide-slate-100" data-testid="category-tree">
            {rows.map(({ node, depth }) => (
              <CategoryRow
                key={node.id}
                node={node}
                depth={depth}
                onAddChild={handleCreate}
                onRename={handleRename}
                onDelete={setConfirmDel}
                newNameState={newName}
                setNewNameState={setNewName}
              />
            ))}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={!!confirmDel}
        title="确认删除"
        message={`确定删除分类「${confirmDel?.name}」吗?`}
        destructive
        confirmText="删除"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}

function CategoryRow({
  node,
  depth,
  onAddChild,
  onRename,
  onDelete,
  newNameState,
  setNewNameState,
}: {
  node: CategoryNode;
  depth: number;
  onAddChild: (parentId: number, name: string) => Promise<void>;
  onRename: (id: number, name: string) => Promise<void>;
  onDelete: (n: CategoryNode) => void;
  newNameState: Record<number | "root", string>;
  setNewNameState: React.Dispatch<React.SetStateAction<Record<number | "root", string>>>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(node.name);

  const submitRename = async () => {
    if (!draft.trim() || draft.trim() === node.name) {
      setEditing(false);
      setDraft(node.name);
      return;
    }
    await onRename(node.id, draft.trim());
    setEditing(false);
  };

  const canHaveChild = node.level < 3;

  return (
    <li
      className="py-2"
      data-testid={`category-row-${node.id}`}
      style={{ paddingLeft: `${depth * 24}px` }}
    >
      <div className="flex items-center gap-2">
        <span className="text-slate-400 text-xs w-6">L{node.level}</span>
        {editing ? (
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={submitRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitRename();
              if (e.key === "Escape") {
                setEditing(false);
                setDraft(node.name);
              }
            }}
            data-testid={`rename-input-${node.id}`}
            className="flex-1 border border-slate-300 rounded px-2 py-1 text-sm"
            autoFocus
            maxLength={30}
          />
        ) : (
          <span
            className="flex-1 text-sm text-slate-800"
            data-testid={`category-name-${node.id}`}
            onDoubleClick={() => setEditing(true)}
          >
            {node.name}
          </span>
        )}
        <button
          onClick={() => setEditing(true)}
          data-testid={`rename-btn-${node.id}`}
          className="text-xs text-slate-500 hover:text-slate-800"
        >
          重命名
        </button>
        {canHaveChild && (
          <details className="relative">
            <summary
              data-testid={`add-child-toggle-${node.id}`}
              className="text-xs text-primary-600 hover:text-primary-800 cursor-pointer list-none"
            >
              + 子分类
            </summary>
            <form
              className="absolute right-0 top-6 z-10 bg-white border border-slate-200 shadow-md rounded p-2 flex gap-1"
              onSubmit={(e) => {
                e.preventDefault();
                const fd = new FormData(e.currentTarget);
                const name = String(fd.get("name") || "").trim();
                if (name) {
                  onAddChild(node.id, name);
                  e.currentTarget.reset();
                }
              }}
            >
              <input
                name="name"
                placeholder="子分类名"
                maxLength={30}
                className="border border-slate-300 rounded px-2 py-1 text-xs w-32"
                data-testid={`add-child-input-${node.id}`}
              />
              <button
                type="submit"
                data-testid={`add-child-submit-${node.id}`}
                className="px-2 py-1 rounded bg-primary-600 text-white text-xs"
              >
                添加
              </button>
            </form>
          </details>
        )}
        <button
          onClick={() => onDelete(node)}
          data-testid={`delete-btn-${node.id}`}
          className="text-xs text-rose-500 hover:text-rose-700"
        >
          删除
        </button>
      </div>
    </li>
  );
}
