import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
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
 * - 任意级别可选(1/2/3 级);后端 R-01 已同步放开,前端不做拦截。
 * - 选中项以路径形式回显(例如: 工程能力 / 软件工程 / 需求分析)。
 */
function CategoryTreeSelect({
  value,
  onChange,
  tree,
  allFlat,
  testId,
  placeholder = "请选择分类",
  clearable = false,
}: {
  value: number | "";
  onChange: (id: number | "") => void;
  tree: CategoryNode[];
  allFlat: CategoryNode[];
  testId?: string;
  placeholder?: string;
  /** 是否允许清除已选项(列表头显示"全部分类"等) */
  clearable?: boolean;
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
          <CategoryTree
            nodes={tree}
            depth={0}
            selectedId={value}
            onSelect={(id) => {
              onChange(id);
              setOpen(false);
            }}
          />
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
}: {
  nodes: CategoryNode[];
  depth: number;
  selectedId: number | "";
  onSelect: (id: number) => void;
}) {
  return (
    <ul className="py-1">
      {nodes.map((n) => (
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
            />
          ) : null}
        </li>
      ))}
    </ul>
  );
}

// ==================== 素材顺序排序器（v1.5+） ====================

/**
 * MaterialSorter：课件表单中的素材拖拽排序组件。
 * - 左栏「素材库」：未被课件引用的素材，点击 + 加入右栏末尾；
 * - 右栏「已选顺序」：使用 @dnd-kit 拖拽 / 键盘排序；× 移除。
 * - 支持鼠标拖拽 + 键盘（Tab 聚焦手柄 → Space 抓取 → ↑/↓ 移动 → Space 释放 → Esc 取消）。
 */
type MaterialSorterProps = {
  available: MaterialItem[];
  selected: MaterialItem[];
  onChange: (next: MaterialItem[]) => void;
  keyword: string;
  onKeywordChange: (kw: string) => void;
  typeFilter: string;
  onTypeFilterChange: (t: string) => void;
};

function MaterialSorter({
  available,
  selected,
  onChange,
  keyword,
  onKeywordChange,
  typeFilter,
  onTypeFilterChange,
}: MaterialSorterProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const selectedIds = selected.map((m) => m.id);

  const filteredAvailable = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return available.filter((m) => {
      if (typeFilter && m.type !== typeFilter) return false;
      if (kw && !m.name.toLowerCase().includes(kw)) return false;
      if (selectedIds.includes(m.id)) return false;
      return true;
    });
  }, [available, keyword, typeFilter, selectedIds]);

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIdx = selectedIds.indexOf(Number(active.id));
    const newIdx = selectedIds.indexOf(Number(over.id));
    if (oldIdx < 0 || newIdx < 0) return;
    onChange(arrayMove(selected, oldIdx, newIdx));
  };

  const add = (m: MaterialItem) => {
    if (selectedIds.includes(m.id)) return;
    onChange([...selected, m]);
  };

  const remove = (id: number) => {
    onChange(selected.filter((m) => m.id !== id));
  };

  const move = (id: number, dir: -1 | 1) => {
    const idx = selectedIds.indexOf(id);
    if (idx < 0) return;
    const target = idx + dir;
    if (target < 0 || target >= selected.length) return;
    onChange(arrayMove(selected, idx, target));
  };

  return (
    <div
      className="grid grid-cols-1 md:grid-cols-2 gap-3"
      data-testid="cw-material-sorter"
    >
      {/* 左栏：素材库 */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <input
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
            placeholder="按素材名称筛选"
            data-testid="cw-material-search"
            className="flex-1 border border-slate-300 rounded px-2 py-1 text-sm"
          />
          <select
            value={typeFilter}
            onChange={(e) => onTypeFilterChange(e.target.value)}
            data-testid="cw-material-type"
            className="border border-slate-300 rounded px-2 py-1 text-sm"
          >
            <option value="">全部类型</option>
            <option value="VIDEO">视频</option>
            <option value="PDF">PDF</option>
            <option value="PPT">PPT</option>
          </select>
        </div>
        <div className="max-h-60 overflow-y-auto border border-slate-200 rounded p-2 bg-slate-50">
          {available.length === 0 && (
            <p className="text-xs text-slate-400">暂无素材</p>
          )}
          {available.length > 0 && filteredAvailable.length === 0 && (
            <p className="text-xs text-slate-400">没有可添加的素材</p>
          )}
          {filteredAvailable.map((m) => (
            <div
              key={m.id}
              data-testid={`cw-material-available-${m.id}`}
              className="flex items-center justify-between text-sm py-1 px-1 hover:bg-white rounded"
            >
              <span className="truncate min-w-0 flex-1">
                {m.name}{" "}
                <span className="text-xs text-slate-400">
                  ({m.type}, {Math.round(m.sizeBytes / 1024)}KB)
                </span>
              </span>
              <button
                type="button"
                onClick={() => add(m)}
                data-testid={`cw-material-add-${m.id}`}
                className="ml-2 text-xs px-2 py-0.5 text-primary-600 hover:bg-primary-50 rounded shrink-0"
              >
                + 添加
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* 右栏：已选顺序 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-slate-600">
            按学习顺序拖拽调整（序号越小越靠前）
          </span>
          <span className="text-xs text-slate-500">
            已选 {selected.length}
          </span>
        </div>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={selectedIds}
            strategy={verticalListSortingStrategy}
          >
            <div
              className="max-h-60 overflow-y-auto border border-slate-200 rounded p-2 bg-white"
              data-testid="cw-material-selected-list"
            >
              {selected.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-4">
                  请从左侧添加素材
                </p>
              )}
              {selected.map((m, idx) => (
                <SortableMaterialRow
                  key={m.id}
                  material={m}
                  index={idx}
                  onRemove={() => remove(m.id)}
                  onMoveUp={() => move(m.id, -1)}
                  onMoveDown={() => move(m.id, 1)}
                  canUp={idx > 0}
                  canDown={idx < selected.length - 1}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </div>
    </div>
  );
}

function SortableMaterialRow({
  material,
  index,
  onRemove,
  onMoveUp,
  onMoveDown,
  canUp,
  canDown,
}: {
  material: MaterialItem;
  index: number;
  onRemove: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  canUp: boolean;
  canDown: boolean;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: material.id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`cw-material-sorter-row-${material.id}`}
      className={`flex items-center gap-2 text-sm py-1 px-1 border rounded mb-1 ${
        isDragging ? "border-primary-300 bg-primary-50" : "border-slate-200"
      }`}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        data-testid={`cw-material-sorter-handle-${material.id}`}
        aria-label={`拖动 ${material.name} 以调整顺序`}
        className="cursor-grab active:cursor-grabbing text-slate-400 hover:text-slate-700 px-1 select-none"
        title="拖拽 / 键盘排序"
      >
        ⋮⋮
      </button>
      <span className="text-xs text-slate-500 w-6 text-center shrink-0">
        {index + 1}
      </span>
      <span className="truncate min-w-0 flex-1">
        {material.name}{" "}
        <span className="text-xs text-slate-400">
          ({material.type}, {Math.round(material.sizeBytes / 1024)}KB)
        </span>
      </span>
      <button
        type="button"
        onClick={onMoveUp}
        disabled={!canUp}
        data-testid={`cw-material-sorter-up-${material.id}`}
        className="text-xs px-1 text-slate-500 hover:text-slate-800 disabled:opacity-30"
        title="上移"
      >
        ▲
      </button>
      <button
        type="button"
        onClick={onMoveDown}
        disabled={!canDown}
        data-testid={`cw-material-sorter-down-${material.id}`}
        className="text-xs px-1 text-slate-500 hover:text-slate-800 disabled:opacity-30"
        title="下移"
      >
        ▼
      </button>
      <button
        type="button"
        onClick={onRemove}
        data-testid={`cw-material-sorter-remove-${material.id}`}
        className="text-xs px-1 text-rose-500 hover:text-rose-700"
        title="移除"
      >
        ×
      </button>
    </div>
  );
}

export function CoursewaresPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams<{ id?: string }>();
  /**
   * 根据 URL 路径判断当前页面模式:
   * - /admin/coursewares/new        → 新建
   * - /admin/coursewares/:id/edit   → 编辑
   * - /admin/coursewares            → 列表
   *
   * 使用 URL 而不是本地 state,是为了让浏览器后退键从新建/编辑页
   * 直接返回列表页,而非回到列表之前的页面(例如分类管理)。
   */
  const mode: Mode = useMemo(() => {
    const p = location.pathname.replace(/\/+$/, "");
    if (p === "/admin/coursewares/new") return "create";
    if (/^\/admin\/coursewares\/\d+\/edit$/.test(p)) return "edit";
    return "list";
  }, [location.pathname]);

  const [editing, setEditing] = useState<CoursewareItem | null>(null);
  const [editingLoading, setEditingLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [filterCat, setFilterCat] = useState<number | "">("");
  const [filterMode, setFilterMode] = useState<"" | "OPEN" | "RESTRICTED">("");
  const [items, setItems] = useState<CoursewareItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  // 分页大小(SIZE=15/页),与 Materials 保持一致;后端 list_paged 已实现 OFFSET/LIMIT + total。
  const [size] = useState(15);
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

  // 进入编辑页时,从接口加载待编辑课件(URL 仅有 id,不再有 courseware 对象)
  useEffect(() => {
    if (mode !== "edit") {
      setEditing(null);
      return;
    }
    const id = params.id ? Number(params.id) : NaN;
    if (!Number.isFinite(id) || id <= 0) {
      toast("无效的课件 id", "error");
      navigate("/admin/coursewares", { replace: true });
      return;
    }
    setEditingLoading(true);
    CoursewareAPI.get(id)
      .then((item) => setEditing(item))
      .catch((e) => {
        toast((e as Error).message || "加载课件失败", "error");
        navigate("/admin/coursewares", { replace: true });
      })
      .finally(() => setEditingLoading(false));
  }, [mode, params.id, navigate]);

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
    navigate("/admin/coursewares/new");
  };

  const startEdit = (cw: CoursewareItem) => {
    navigate(`/admin/coursewares/${cw.id}/edit`);
  };

  const backToList = () => {
    navigate("/admin/coursewares");
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
    // 编辑模式下,待编辑课件从接口加载;加载未完成前不渲染表单,
    // 避免出现表单先以空 initial 闪烁再被覆盖的抖动。
    if (mode === "edit" && (editingLoading || !editing)) {
      return (
        <div className="max-w-3xl mx-auto bg-white rounded-lg shadow-sm border border-slate-200 p-6 text-slate-500">
          {editingLoading ? "正在加载课件…" : "未找到待编辑课件"}
        </div>
      );
    }
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
  // v1.5+: selectedMaterials 保持顺序（课件内的展示顺序），
  // materialIds 仅在提交时从 selectedMaterials 派生。
  const materialsById = useMemo(() => {
    const m = new Map<number, MaterialItem>();
    materials.forEach((mi) => m.set(mi.id, mi));
    initial?.materials?.forEach((mi) => {
      if (!m.has(mi.id)) {
        m.set(mi.id, {
          id: mi.id,
          name: mi.name,
          type: mi.type as MaterialItem["type"],
          sizeBytes: mi.sizeBytes,
          duration: mi.duration ?? null,
          uploadedAt: null,
          referenced: true,
          downloadUrl: mi.downloadUrl ?? "",
        });
      }
    });
    return m;
  }, [materials, initial]);
  const [selectedMaterials, setSelectedMaterials] = useState<MaterialItem[]>(() => {
    if (!initial) return [];
    return (initial.materials ?? [])
      .map((m) => materialsById.get(m.id))
      .filter((m): m is MaterialItem => Boolean(m));
  });
  const [tokenIds, setTokenIds] = useState<number[]>(initial?.tokenIds ?? []);
  const [saving, setSaving] = useState(false);

  // 选择器内的本地筛选状态(客户端过滤,避免加载量过大时难以查找)
  const [materialKeyword, setMaterialKeyword] = useState("");
  const [materialTypeFilter, setMaterialTypeFilter] = useState<string>("");
  const [tokenKeyword, setTokenKeyword] = useState("");

  const filteredTokens = useMemo(() => {
    const kw = tokenKeyword.trim().toLowerCase();
    if (!kw) return tokens;
    return tokens.filter((t) => t.label.toLowerCase().includes(kw));
  }, [tokens, tokenKeyword]);

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
    // 课件可挂接到分类树的任意层级(1 级 / 2 级 / 3 级叶子)节点;
    // 不再做 level 拦截,允许中间层级。后端校验已同步放开。
    if (accessMode === "RESTRICTED" && tokenIds.length === 0) {
      toast("受限课件必须绑定至少 1 个令牌", "error");
      return;
    }
    setSaving(true);
    try {
      // materialIds 由 selectedMaterials 按当前顺序导出
      const orderedMaterialIds = selectedMaterials.map((m) => m.id);
      const payload = {
        title: trimmedTitle,
        author: author.trim() || undefined,
        categoryId: Number(categoryId),
        description: description || undefined,
        accessMode,
        tagIds,
        materialIds: orderedMaterialIds,
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
        {initial ? "编辑课件" : "新建课件"}
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
            placeholder="请选择分类"
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

        {accessMode === "RESTRICTED" && (
          <div data-testid="cw-tokens-block">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-700">
                绑定令牌 * (至少 1 个)
              </span>
              <span className="text-xs text-slate-500">
                已选 {tokenIds.length} / 共 {tokens.length}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <input
                value={tokenKeyword}
                onChange={(e) => setTokenKeyword(e.target.value)}
                placeholder="按令牌标签筛选"
                data-testid="cw-token-search"
                className="flex-1 border border-slate-300 rounded px-2 py-1 text-sm"
              />
              {tokenKeyword && (
                <button
                  type="button"
                  onClick={() => setTokenKeyword("")}
                  className="text-xs text-slate-500 hover:text-slate-700"
                >
                  清除
                </button>
              )}
            </div>
            <div className="mt-1 flex flex-col gap-1 max-h-40 overflow-y-auto border border-slate-200 rounded p-2">
              {tokens.length === 0 && (
                <span className="text-xs text-slate-400">
                  暂无令牌,请先到「访问令牌」创建
                </span>
              )}
              {tokens.length > 0 && filteredTokens.length === 0 && (
                <span className="text-xs text-slate-400">
                  没有匹配的令牌
                </span>
              )}
              {filteredTokens.map((t) => (
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
                  <span className="ml-2 text-xs text-slate-400">
                    (被 {t.coursewareCount} 个课件引用)
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-700">标签</span>
            <span className="text-xs text-slate-500">
              已选 {tagIds.length} / 共 {tags.length}
            </span>
          </div>
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
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-700">关联素材（学习顺序）</span>
            <span className="text-xs text-slate-500">
              已选 {selectedMaterials.length} / 共 {materials.length}
            </span>
          </div>
          <MaterialSorter
            available={materials}
            selected={selectedMaterials}
            onChange={setSelectedMaterials}
            keyword={materialKeyword}
            onKeywordChange={setMaterialKeyword}
            typeFilter={materialTypeFilter}
            onTypeFilterChange={setMaterialTypeFilter}
          />
        </div>
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