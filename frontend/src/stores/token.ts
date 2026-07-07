/** 已解锁的 token 哈希记忆(localStorage)。浏览器隐私模式回退到内存。 */
import { create } from "zustand";

type State = {
  /** coursewareId -> tokenHash(已解锁) */
  unlockedByCourseware: Record<number, string>;
  unlock: (coursewareId: number, tokenHash: string) => void;
  has: (coursewareId: number) => boolean;
  refresh: () => void;
};

const STORAGE_KEY = "lh_unlocked_tokens";

function load(): Record<number, string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const obj = JSON.parse(raw) as Record<string, string>;
    const out: Record<number, string> = {};
    for (const [k, v] of Object.entries(obj)) {
      const n = Number(k);
      if (Number.isFinite(n)) out[n] = v;
    }
    return out;
  } catch {
    return {};
  }
}

function save(data: Record<number, string>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    /* 隐私模式无 storage,跳过 */
  }
}

export const useTokenStore = create<State>((set, get) => ({
  unlockedByCourseware: {},
  unlock: (coursewareId, tokenHash) => {
    const cur = get().unlockedByCourseware;
    const next = { ...cur, [coursewareId]: tokenHash };
    save(next);
    set({ unlockedByCourseware: next });
  },
  has: (coursewareId) => Boolean(get().unlockedByCourseware[coursewareId]),
  refresh: () => set({ unlockedByCourseware: load() }),
}));

/** 初始化:从 localStorage 灌入。 */
export function hydrateTokenStore(): void {
  useTokenStore.setState({ unlockedByCourseware: load() });
}
