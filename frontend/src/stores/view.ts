/** 前台视图状态:由 URL query 同步(view + q + id + cw)。 */
import { create } from "zustand";

export type View = "home" | "result" | "locked" | "detail" | "viewer";

const VIEW_WHITELIST: ReadonlyArray<View> = [
  "home",
  "result",
  "locked",
  "detail",
  "viewer",
];

type ViewState = {
  view: View;
  q: string;
  id: number | null;
  /** 课件 ID（仅 viewer 页使用，便于返回 P-DETAIL）。 */
  coursewareId: number | null;
  /** 设置:同步到 URL。 */
  go: (
    next: Partial<Pick<ViewState, "view" | "q" | "id" | "coursewareId">>,
  ) => void;
};

function readUrl(): {
  view: View;
  q: string;
  id: number | null;
  coursewareId: number | null;
} {
  if (typeof window === "undefined") {
    return { view: "home", q: "", id: null, coursewareId: null };
  }
  const p = new URLSearchParams(window.location.search);
  const viewRaw = p.get("view") as View | null;
  let view: View = VIEW_WHITELIST.includes(viewRaw as View)
    ? (viewRaw as View)
    : "home";
  const q = p.get("q") ?? "";
  const idRaw = p.get("id");
  const id = idRaw && /^\d+$/.test(idRaw) ? Number(idRaw) : null;
  const cwRaw = p.get("cw");
  const coursewareId =
    cwRaw && /^\d+$/.test(cwRaw) ? Number(cwRaw) : null;
  // 启发式:有 id → detail/viewer(若未显式 locked);有 q → result
  if (view === "home") {
    if (id != null) {
      // viewer 是显式 view,否则降级为 detail
      view = coursewareId != null ? "viewer" : "detail";
    } else if (q) {
      view = "result";
    }
  }
  return { view, q, id, coursewareId };
}

let urlTimer: number | null = null;

export const useViewStore = create<ViewState>((set, get) => ({
  view: "home",
  q: "",
  id: null,
  coursewareId: null,
  go: (next) => {
    const cur = get();
    const merged = {
      view: next.view ?? cur.view,
      q: next.q ?? cur.q,
      id: next.id ?? cur.id,
      coursewareId: next.coursewareId ?? cur.coursewareId,
    };
    set(merged);
    if (urlTimer != null) window.clearTimeout(urlTimer);
    urlTimer = window.setTimeout(() => {
      const params = new URLSearchParams();
      if (merged.view !== "home") params.set("view", merged.view);
      if (merged.q) params.set("q", merged.q);
      if (merged.id != null) params.set("id", String(merged.id));
      if (merged.coursewareId != null)
        params.set("cw", String(merged.coursewareId));
      const search = params.toString();
      const url = `${window.location.pathname}${search ? "?" + search : ""}`;
      window.history.replaceState(null, "", url);
    }, 0);
  },
}));

/** 初始化:把 URL 当前状态灌入 store。 */
export function hydrateViewFromUrl(): void {
  const { view, q, id, coursewareId } = readUrl();
  useViewStore.setState({ view, q, id, coursewareId });
}

/** 任意时刻从 URL 重新同步 store(供 React Router location 变化触发)。 */
export function syncViewFromUrl(): void {
  const { view, q, id, coursewareId } = readUrl();
  const cur = useViewStore.getState();
  if (
    cur.view !== view ||
    cur.q !== q ||
    cur.id !== id ||
    cur.coursewareId !== coursewareId
  ) {
    useViewStore.setState({ view, q, id, coursewareId });
  }
}

/** 监听浏览器前进/后退(popstate)。 */
export function bindViewToPopState(): () => void {
  const onPop = () => {
    const { view, q, id, coursewareId } = readUrl();
    useViewStore.setState({ view, q, id, coursewareId });
  };
  window.addEventListener("popstate", onPop);
  return () => window.removeEventListener("popstate", onPop);
}