import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AccessTokenAPI,
  CategoryAPI,
  type AccessTokenItem,
  type CategoryNode,
  type CoursewareItem,
  CoursewareAPI,
  type MaterialItem,
  MaterialAPI,
  type TagItem,
  TagAPI,
} from "@/api";
import { toast } from "@/stores/toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";

function categoryPath(node: CategoryNode, all: CategoryNode[]): string {
  const parts: string[] = [];
  let cur: CategoryNode | undefined = node;
  while (cur) {
    parts.unshift(cur.name);
    cur = cur.parentId ? all.find((n) => n.id === cur!.parentId) : undefined;
  }
  return parts.join(" / ");
}

type Mode = "list" | "create" | "edit";

/** 层级对应的色块(浅米黄 / 中黄 / 紫)。 */
function levelSwatch(level: number): string {
  switch (level) {
    case 1:
      return "bg-amber-100";
    case 2:
      return "bg-amber-300";
    default:
      return "bg-violet-300";
  }
}

/**
 * 树状分类选择器:点击触发器弹出层,递归渲染树节点,选中后回调。
 * - 任意级别可选(1/2/3 级)
 * - 选中项以路径形式回显(例如: 工程能力 / 软件工程 / 需求分析)
 */
function CategoryTreeSelect({
  value,
  onChange,
  tree,
  allFlat,
  testId,
  placeholder = "请选择分类",
  clearable = false,
  /**
   * 仅允许选择叶子节点(L3)。
   * - 启用后:非叶子节点(L1/L2)渲染为只读 header,鼠标悬浮无 hover 高亮,点击不会触发选择;
   * - 配合业务规则 R-02(课件必须挂到 3 级叶子),让用户根本选不到非叶子,
   *   避免提交时再弹"必须挂到 3 级"的错误。
   */
  leafOnly = false,
  /**
   * 当 leafOnly=true 且全树没有叶子时,展示给用户的引导文案。
   * (例如提示先去分类管理建 3 级叶子)
   */
  emptyText,
}: {
  value: number | "";
  onChange: (id: number | "") => void;
  tree: CategoryNode[];
  allFlat: CategoryNode[];
  testId?: string;
  placeholder?: string;
  /** 是否允许清除已选项(列表头显示"全部分类"等) */
  clearable?: boolean;
  leafOnly?: boolean;
  emptyText?: string;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const current = value === "" ? null : allFlat.find((n) => n.id === value);
  const display = current ? categoryPath(current, allFlat) : "";

  // leafOnly 模式下,统计全树叶子总数:为 0 时显示引导文案
  const leafCount = leafOnly
    ? allFlat.filter((n) => n.level === 3).length
    : -1;
  const showEmpty = leafOnly && leafCount === 0;

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        data-testid={testId}
        className={`mt-1 w-full border rounded-md px-3 py-2 text-left bg-white hover:border-slate-400 flex items-center gap-2 ${
          open ? "border-primary-500 ring-2 ring-primary-200" : "border-slate-300"
        }`}
      >
        {current ? (
          <>
            <span
              className={`inline-block w-3 h-3 rounded-sm ${levelSwatch(current.level)} shrink-0`}
              aria-hidden
            />
            <span className="flex-1 truncate text-slate-800">{display}</span>
          </>
        ) : (
          <span className="flex-1 truncate text-slate-400">{placeholder}</span>
        )}
        <span className="text-slate-400 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div
          className="absolute z-20 mt-1 w-full max-h-72 overflow-y-auto bg-white border border-slate-200 rounded-md shadow-lg"
          data-testid={testId ? `${testId}-tree` : undefined}
        >
          {clearable && (
            <button
              type="button"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
              className={`w-full text-left text-sm px-3 py-1.5 hover:bg-slate-50 flex items-center gap-2 ${
                value === "" ? "bg-primary-50 text-primary-700" : "text-slate-700"
              }`}
            >
              <span className="inline-block w-3 h-3 rounded-sm border border-dashed border-slate-300 shrink-0" />
              <span className="flex-1">{placeholder}</span>
            </button>
          )}
          {showEmpty ? (
            <div className="px-3 py-4 text-sm text-rose-500 text-center">
              {emptyText ?? "暂无 3 级叶子分类,请先到分类管理创建"}
            </div>
          ) : (
            <CategoryTree
              nodes={tree}
              depth={0}
              selectedId={value}
              onSelect={(id) => {
                onChange(id);
                setOpen(false);
              }}
              leafOnly={leafOnly}
            />
          )}
        </div>
      )}
    </div>
  );
}

function CategoryTree({
  nodes,
  depth,
  selectedId,
  onSelect,
  leafOnly = false,
}: {
  nodes: CategoryNode[];
  depth: number;
  selectedId: number | "";
  onSelect: (id: number) => void;
  leafOnly?: boolean;
}) {
  return (
    <ul className="py-1">
      {nodes.map((n) => {
        const isLeaf = n.level === 3;
        // leafOnly 模式:非叶子节点渲染为只读 header(不可点击)
        if (leafOnly && !isLeaf) {
          return (
            <li key={n.id}>
              <div
                className="w-full text-left text-sm py-1.5 flex items-center gap-2 text-slate-500 cursor-default select-none"
                style={{ paddingLeft: `${depth * 16 + 12}px`, paddingRight: "12px" }}
                title={`${n.name} (L${n.level} · 仅供浏览,请选择下级叶子)`}
              >
                <span
                  className={`inline-block w-3 h-3 rounded-sm ${levelSwatch(n.level)} shrink-0`}
                  aria-hidden
                />
                <span className="flex-1 truncate font-medium">{n.name}</span>
                <span className="text-[10px] text-slate-400 shrink-0">L{n.level}</span>
              </div>
              {n.children?.length ? (
                <CategoryTree
                  nodes={n.children}
                  depth={depth + 1}
                  selectedId={selectedId}
                  onSelect={onSelect}
                  leafOnly={leafOnly}
                />
              ) : null}
            </li>
          );
        }
        return (
          <li key={n.id}>
            <button
              type="button"
              onClick={() => onSelect(n.id)}
              data-testid={`cw-cat-tree-option-${n.id}`}
              className={`w-full text-left text-sm py-1.5 hover:bg-primary-50 flex items-center gap-2 ${
                n.id === selectedId ? "bg-primary-50 text-primary-700 font-medium" : "text-slate-700"
              }`}
              style={{ paddingLeft: `${depth * 16 + 12}px`, paddingRight: "12px" }}
            >
              <span
                className={`inline-block w-3 h-3 rounded-sm ${levelSwatch(n.level)} shrink-0`}
                aria-hidden
              />
              <span className="flex-1 truncate">{n.name}</span>
              <span className="text-[10px] text-slate-400 shrink-0">L{n.level}</span>
            </button>
            {n.children?.length ? (
              <CategoryTree
                nodes={n.children}
                depth={depth + 1}
                selectedId={selectedId}
                onSelect={onSelect}
                leafOnly={leafOnly}
              />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function CoursewaresPage() {
  const [mode, setMode] = useState<Mode>("list");
  const [editing, setEditing] = useState<CoursewareItem | null>(null);
  const [keyword, setKeyword] = useState("");
  const [filterCat, setFilterCat] = useState<number | "">("");
  const [filterMode, setFilterMode] = useState<"" | "OPEN" | "RESTRICTED">("");
  const [items, setItems] = useState<CoursewareItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [size] = useState(20);
  const [loading, setLoading] = useState(false);
  const [confirmDel, setConfirmDel] = useState<CoursewareItem | null>(null);

  // 关联数据(表单用)
  const [categoryTree, setCategoryTree] = useState<CategoryNode[]>([]);
  const [tags, setTags] = useState<TagItem[]>([]);
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [tokens, setTokens] = useState<AccessTokenItem[]>([]);

  const loadAux = useCallback(async () => {
    const [cat, tagPage, matPage, tok] = await Promise.all([
      CategoryAPI.list(),
      TagAPI.list({ size: 200 }),
      MaterialAPI.list({ size: 200 }),
      AccessTokenAPI.list({ size: 200 }),
    ]);
    setCategoryTree(cat);
    setTags(tagPage.items);
    setMaterials(matPage.items);
    setTokens(tok.items);
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await CoursewareAPI.list({
        keyword: keyword || undefined,
        categoryId: filterCat === "" ? undefined : Number(filterCat),
        accessMode: filterMode || undefined,
        page,
        size,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      toast((e as Error).message || "加载失败", "error");
    } finally {
      setLoading(false);
    }
  }, [keyword, filterCat, filterMode, page, size]);

  useEffect(() => {
    loadAux();
  }, [loadAux]);

  useEffect(() => {
    if (mode === "list") reload();
  }, [reload, mode]);

  const allCategoriesFlat = useMemo(() => {
    const out: CategoryNode[] = [];
    const visit = (arr: CategoryNode[]) => {
      for (const n of arr) {
        out.push(n);
        if (n.children?.length) visit(n.children);
      }
    };
    visit(categoryTree);
    return out;
  }, [categoryTree]);

  const startCreate = () => {
    setEditing(null);
    setMode("create");
  };

  const startEdit = (cw: CoursewareItem) => {
    setEditing(cw);
    setMode("edit");
  };

  const backToList = () => {
    setMode("list");
    setEditing(null);
    reload();
  };

  const handleDelete = async () => {
    if (!confirmDel) return;
    try {
      await CoursewareAPI.remove(confirmDel.id);
      toast("已删除", "success");
      reload();
    } catch (e) {
      toast((e as Error).message || "删除失败", "error");
    } finally {
      setConfirmDel(null);
    }
  };

  if (mode !== "list") {
    return (
      <CoursewareForm
        initial={editing}
        categoryTree={categoryTree}
        allCategories={allCategoriesFlat}
        tags={tags}
        materials={materials}
        tokens={tokens}
        onCancel={backToList}
        onSaved={() => {
          toast("已保存", "success");
          backToList();
        }}
      />
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">课件管理</h1>
          <p className="text-sm text-slate-500 mt-1">共 {total} 条</p>
        </div>
        <button
          onClick={startCreate}
          data-testid="cw-new-btn"
          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-md"
        >
          新建课件
        </button>
      </header>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4 mb-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <input
          value={keyword}
          onChange={(e) => {
            setKeyword(e.target.value);
            setPage(1);
          }}
          placeholder="搜索标题/作者/描述"
          className="border border-slate-300 rounded-md px-3 py-2"
        />
        <CategoryTreeSelect
          value={filterCat}
          onChange={(id) => {
            setFilterCat(id === "" ? "" : id);
            setPage(1);
          }}
          tree={categoryTree}
          allFlat={allCategoriesFlat}
          testId="filter-category"
          placeholder="全部分类"
          clearable
        />
        <select
          value={filterMode}
          onChange={(e) => {
            setFilterMode(e.target.value as "" | "OPEN" | "RESTRICTED");
            setPage(1);
          }}
          className="border border-slate-300 rounded-md px-3 py-2"
        >
          <option value="">全部访问模式</option>
          <option value="OPEN">开放</option>
          <option value="RESTRICTED">受限</option>
        </select>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-left">
            <tr>
              <th className="px-4 py-2">ID</th>
              <th className="px-4 py-2">标题</th>
              <th className="px-4 py-2">分类</th>
              <th className="px-4 py-2">访问</th>
              <th className="px-4 py-2">标签</th>
              <th className="px-4 py-2">绑定令牌</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  加载中...
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  暂无数据
                </td>
              </tr>
            )}
            {!loading &&
              items.map((cw) => (
                <tr
                  key={cw.id}
                  data-testid={`cw-row-${cw.id}`}
                  className="border-t border-slate-100 hover:bg-slate-50"
                >
                  <td className="px-4 py-2 text-slate-700">{cw.id}</td>
                  <td className="px-4 py-2 font-medium text-slate-800">
                    {cw.title}
                    {cw.author && (
                      <span className="ml-2 text-xs text-slate-500">
                        · {cw.author}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {cw.categoryName ?? "-"}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        cw.accessMode === "RESTRICTED"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {cw.accessMode === "RESTRICTED" ? "受限" : "开放"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {cw.tagNames.length ? cw.tagNames.join(", ") : "-"}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {cw.tokenIds.length}
                  </td>
                  <td className="px-4 py-2 text-right space-x-2">
                    <button
                      onClick={() => startEdit(cw)}
                      data-testid={`cw-edit-${cw.id}`}
                      className="px-2 py-1 text-primary-600 hover:bg-primary-50 rounded"
                    >
                      编辑
                    </button>
                    <button
                      onClick={() => setConfirmDel(cw)}
                      data-testid={`cw-del-${cw.id}`}
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

      {total > size && (
        <div className="mt-4 flex justify-center gap-2">
          <button
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="px-3 py-1 border rounded disabled:opacity-40"
          >
            上一页
          </button>
          <span className="px-3 py-1 text-slate-600">
            第 {page} 页 / 共 {Math.ceil(total / size)} 页
          </span>
          <button
            disabled={page * size >= total}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1 border rounded disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      )}

      <ConfirmDialog
        open={confirmDel !== null}
        title="删除课件"
        message={
          confirmDel ? `确认删除 "${confirmDel.title}"?关联数据将一并清除。` : ""
        }
        confirmText="删除"
        tone="danger"
        onConfirm={handleDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}

// ==================== 表单 ====================

type FormProps = {
  initial: CoursewareItem | null;
  categoryTree: CategoryNode[];
  allCategories: CategoryNode[];
  tags: TagItem[];
  materials: MaterialItem[];
  tokens: AccessTokenItem[];
  onCancel: () => void;
  onSaved: () => void;
};

function CoursewareForm({
  initial,
  categoryTree,
  allCategories,
  tags,
  materials,
  tokens,
  onCancel,
  onSaved,
}: FormProps) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [author, setAuthor] = useState(initial?.author ?? "");
  const [categoryId, setCategoryId] = useState<number | "">(
    initial?.categoryId ?? "",
  );
  const [description, setDescription] = useState(initial?.description ?? "");
  const [accessMode, setAccessMode] = useState<"OPEN" | "RESTRICTED">(
    initial?.accessMode ?? "OPEN",
  );
  const [tagIds, setTagIds] = useState<number[]>(initial?.tagIds ?? []);
  const [materialIds, setMaterialIds] = useState<number[]>(
    initial?.materialIds ?? [],
  );
  const [tokenIds, setTokenIds] = useState<number[]>(initial?.tokenIds ?? []);
  const [saving, setSaving] = useState(false);

  const pathOf = (id: number) => {
    const node = allCategories.find((c) => c.id === id);
    return node ? categoryPath(node, allCategories) : "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      toast("请填写标题", "error");
      return;
    }
    if (categoryId === "") {
      toast("请选择分类", "error");
      return;
    }
    // 业务规则 R-02:课件必须挂到 3 级叶子分类。
    // 前端树选择器已用 leafOnly 模式,只能选到 L3 叶子;这里不再做 level 拦截
    // (避免用户看到「必须挂到 3 级」的错误)。后端 R-02 校验仍作为最后防线。
    if (accessMode === "RESTRICTED" && tokenIds.length === 0) {
      toast("受限课件必须绑定至少 1 个令牌", "error");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        title: trimmedTitle,
        author: author.trim() || undefined,
        categoryId: Number(categoryId),
        description: description || undefined,
        accessMode,
        tagIds,
        materialIds,
        tokenIds: accessMode === "RESTRICTED" ? tokenIds : [],
      };
      if (initial) {
        await CoursewareAPI.update(initial.id, payload);
      } else {
        await CoursewareAPI.create(payload);
      }
      onSaved();
    } catch (e) {
      toast((e as Error).message || "保存失败", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="max-w-3xl mx-auto bg-white rounded-lg shadow-sm border border-slate-200 p-6"
      data-testid="cw-form"
    >
      <h2 className="text-xl font-bold text-slate-800 mb-4">
        {initial ? `编辑课件 #${initial.id}` : "新建课件"}
      </h2>

      <div className="space-y-4">
        <label className="block">
          <span className="text-sm text-slate-700">标题 *</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="cw-title"
            maxLength={100}
            className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm text-slate-700">作者</span>
          <input
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            maxLength={50}
            className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2"
          />
        </label>

        <div>
          <span className="text-sm text-slate-700">分类 *</span>
          <CategoryTreeSelect
            value={categoryId}
            onChange={(id) => setCategoryId(id)}
            tree={categoryTree}
            allFlat={allCategories}
            testId="cw-category"
            leafOnly
            placeholder="请选择 3 级叶子分类"
          />
          {categoryTree.length === 0 && (
            <span
              className="mt-1 block text-xs text-rose-600"
              data-testid="cw-category-empty-hint"
            >
              ⚠ 当前没有分类,请先到
              <a
                href="/admin/categories"
                className="ml-1 underline hover:text-rose-800"
                onClick={(e) => {
                  e.preventDefault();
                  window.location.href = "/admin/categories";
                }}
              >
                分类管理
              </a>
              中创建。
            </span>
          )}
        </div>

        <label className="block">
          <span className="text-sm text-slate-700">描述</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm text-slate-700">访问模式</span>
          <div className="mt-1 flex gap-4">
            <label className="inline-flex items-center">
              <input
                type="radio"
                name="accessMode"
                value="OPEN"
                checked={accessMode === "OPEN"}
                onChange={() => setAccessMode("OPEN")}
                data-testid="cw-mode-open"
              />
              <span className="ml-2">开放</span>
            </label>
            <label className="inline-flex items-center">
              <input
                type="radio"
                name="accessMode"
                value="RESTRICTED"
                checked={accessMode === "RESTRICTED"}
                onChange={() => setAccessMode("RESTRICTED")}
                data-testid="cw-mode-restricted"
              />
              <span className="ml-2">受限(需绑定令牌)</span>
            </label>
          </div>
        </label>

        <div>
          <span className="text-sm text-slate-700">标签</span>
          <div className="mt-1 flex flex-wrap gap-2 max-h-32 overflow-y-auto border border-slate-200 rounded p-2">
            {tags.length === 0 && (
              <span className="text-xs text-slate-400">暂无标签</span>
            )}
            {tags.map((t) => (
              <label key={t.id} className="inline-flex items-center text-sm">
                <input
                  type="checkbox"
                  checked={tagIds.includes(t.id)}
                  onChange={(e) => {
                    if (e.target.checked) setTagIds((s) => [...s, t.id]);
                    else setTagIds((s) => s.filter((x) => x !== t.id));
                  }}
                />
                <span className="ml-1">{t.name}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <span className="text-sm text-slate-700">关联素材</span>
          <div className="mt-1 flex flex-col gap-1 max-h-40 overflow-y-auto border border-slate-200 rounded p-2">
            {materials.length === 0 && (
              <span className="text-xs text-slate-400">暂无素材</span>
            )}
            {materials.map((m) => (
              <label key={m.id} className="inline-flex items-center text-sm">
                <input
                  type="checkbox"
                  checked={materialIds.includes(m.id)}
                  onChange={(e) => {
                    if (e.target.checked)
                      setMaterialIds((s) => [...s, m.id]);
                    else setMaterialIds((s) => s.filter((x) => x !== m.id));
                  }}
                />
                <span className="ml-1">
                  {m.name}{" "}
                  <span className="text-xs text-slate-400">
                    ({m.type}, {Math.round(m.sizeBytes / 1024)}KB)
                  </span>
                </span>
              </label>
            ))}
          </div>
        </div>

        {accessMode === "RESTRICTED" && (
          <div>
            <span className="text-sm text-slate-700">
              绑定令牌 * (至少 1 个)
            </span>
            <div className="mt-1 flex flex-col gap-1 max-h-40 overflow-y-auto border border-slate-200 rounded p-2">
              {tokens.length === 0 && (
                <span className="text-xs text-slate-400">
                  暂无令牌,请先到「访问令牌」创建
                </span>
              )}
              {tokens.map((t) => (
                <label
                  key={t.id}
                  className="inline-flex items-center text-sm"
                >
                  <input
                    type="checkbox"
                    checked={tokenIds.includes(t.id)}
                    onChange={(e) => {
                      if (e.target.checked)
                        setTokenIds((s) => [...s, t.id]);
                      else setTokenIds((s) => s.filter((x) => x !== t.id));
                    }}
                  />
                  <span className="ml-1">{t.label}</span>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 border border-slate-300 rounded-md hover:bg-slate-50"
        >
          取消
        </button>
        <button
          type="submit"
          disabled={saving}
          data-testid="cw-save"
          className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-md"
        >
          {saving ? "保存中..." : "保存"}
        </button>
      </div>
    </form>
  );
}