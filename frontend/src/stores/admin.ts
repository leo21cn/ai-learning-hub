import { create } from "zustand";
import { apiClient } from "@/api/client";

export type AdminSession = {
  token: string;
  expiresAt: string;
};

type AdminState = {
  session: AdminSession | null;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  restore: () => void;
};

const STORAGE_KEY = "lh_admin_session";

function load(): AdminSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as AdminSession;
    if (new Date(data.expiresAt).getTime() <= Date.now()) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

export const useAdminStore = create<AdminState>((set) => ({
  session: null,
  loading: false,
  login: async (token: string) => {
    set({ loading: true });
    try {
      const resp = await apiClient.post<{
        adminId: string;
        expiresAt: string;
      }>("/auth/admin", { token });
      const sess: AdminSession = {
        token: resp.data.adminId === "single-admin" ? token : token,
        expiresAt: resp.data.expiresAt,
      };
      // 持久化 JWT(后端返回的 token 在 adminId 字段里携带不到,实际由
      // 后端 Set-Cookie LH_ADMIN_SESSION 自动注入;此处只存 expiresAt)
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ token: "(cookie)", expiresAt: sess.expiresAt } satisfies AdminSession),
      );
      set({ session: sess, loading: false });
    } catch (e) {
      set({ loading: false });
      throw e;
    }
  },
  logout: async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      /* 忽略 */
    }
    localStorage.removeItem(STORAGE_KEY);
    set({ session: null });
  },
  restore: () => set({ session: load() }),
}));
