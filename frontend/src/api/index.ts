/** 后端管理 API 包装：统一解 envelope，直接返回 data。 */
import { apiClient } from "./client";
import { useTokenStore } from "@/stores/token";
import { useViewStore } from "@/stores/view";

const unwrap = <T>(p: Promise<{ data: T }>): Promise<T> => p.then((r) => r.data);

/** 取 coursewareId 对应的已记忆 tokenHash(若有)，作为 X-Token-Hash 头。
 *
 * 为什么用 header 不用 cookie：
 * - unlock 接口同时会 Set-Cookie，但浏览器 fetch 在同一个微任务/任务里
 *   写 Set-Cookie 的时序与下一次 GET 请求之间存在窗口期。若 P-DETAIL 的
 *   fetch 紧跟 unlock.then，浏览器可能还没把 cookie 写入 CookieJar，导致
 *   后端读不到 lh_token_hash，返 403，前端跳回 P-LOCKED——表现为
 *   "输入令牌两次才能打开课件页面"。
 * - 直接从 useTokenStore 拿 tokenHash(由 Locked.unlock 同步写入)，
 *   作为 X-Token-Hash 头传入，与 Set-Cookie 完全解耦。
 */
function tokenHashHeaders(coursewareId: number | null): Record<string, string> {
  if (coursewareId == null) return {};
  const hash = useTokenStore.getState().unlockedByCourseware[coursewareId];
  return hash ? { "X-Token-Hash": hash } : {};
}

// ===== Auth =====
export const AuthAPI = {
  adminLogin: (token: string) =>
    unwrap(
      apiClient.post<{ adminId: string; expiresAt: string }>("/auth/admin", { token }),
    ),
  adminLogout: () => unwrap(apiClient.post("/auth/logout")),
};

// ===== Categories =====
export type CategoryNode = {
  id: number;
  name: string;
  level: number;
  parentId: number | null;
  children: CategoryNode[];
};

export const CategoryAPI = {
  list: () => unwrap(apiClient.get<CategoryNode[]>("/admin/categories")),
  create: (name: string, parentId?: number) =>
    unwrap(apiClient.post("/admin/categories", { name, parentId: parentId ?? null })),
  rename: (id: number, name: string) =>
    unwrap(apiClient.put(`/admin/categories/${id}`, { name })),
  remove: (id: number) => unwrap(apiClient.delete(`/admin/categories/${id}`)),
};

// ===== Tags =====
export type TagItem = {
  id: number;
  name: string;
  coursewareCount: number;
  createdAt: string | null;
};
export type TagPaged = { page: number; size: number; total: number; items: TagItem[] };

export const TagAPI = {
  list: (params: { keyword?: string; page?: number; size?: number } = {}) =>
    unwrap(apiClient.get<TagPaged>("/admin/tags", { params })),
  create: (name: string) => unwrap(apiClient.post("/admin/tags", { name })),
  rename: (id: number, name: string) =>
    unwrap(apiClient.put(`/admin/tags/${id}`, { name })),
  remove: (id: number) => unwrap(apiClient.delete(`/admin/tags/${id}`)),
};

// ===== Materials =====
export type MaterialItem = {
  id: number;
  name: string;
  type: "VIDEO" | "PDF" | "PPT" | "ZIP";
  sizeBytes: number;
  duration: string | null;
  uploadedAt: string | null;
  referenced: boolean;
  downloadUrl: string;
};
export type MaterialPaged = {
  page: number;
  size: number;
  total: number;
  items: MaterialItem[];
};

export const MaterialAPI = {
  list: (
    params: { keyword?: string; type?: string; page?: number; size?: number } = {},
  ) => unwrap(apiClient.get<MaterialPaged>("/admin/materials", { params })),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return unwrap(
      apiClient.post<{ id: number; name: string; type: string; sizeBytes: number }>(
        "/admin/materials",
        fd,
        {
          headers: { "Content-Type": "multipart/form-data" },
          // 大文件上传(5–10Mbps 家用网络上 200MB 需 150–300s);
          // 单次请求覆盖默认 30s 客户端超时,与后端/nginx 600s 对齐,剩余 5 分钟冗余。
          timeout: 15 * 60 * 1000,
          onUploadProgress: (evt) => {
            if (!evt.total) return;
            // 可在此处将进度冒泡给上层组件用于 UI 展示
            void evt;
          },
        },
      ),
    );
  },
  remove: (id: number) => unwrap(apiClient.delete(`/admin/materials/${id}`)),
  fileUrl: (id: number) => `/api/admin/materials/${id}/file`,
};

// ===== Access Tokens =====
export type AccessTokenItem = {
  id: number;
  label: string;
  valueHash: string;
  coursewareCount: number;
  createdAt: string | null;
  regeneratedAt: string | null;
};
export type AccessTokenCreated = {
  id: string;
  label: string;
  value: string; // 仅创建/重新生成时一次性返回
  valueHash: string;
  createdAt: string | null;
  regeneratedAt: string | null;
};
export type AccessTokenPaged = {
  page: number;
  size: number;
  total: number;
  items: AccessTokenItem[];
};

export const AccessTokenAPI = {
  list: (params: { keyword?: string; page?: number; size?: number } = {}) =>
    unwrap(apiClient.get<AccessTokenPaged>("/admin/access-tokens", { params })),
  create: (label: string) =>
    unwrap(
      apiClient.post<AccessTokenCreated>("/admin/access-tokens", { label }),
    ),
  regenerate: (id: number) =>
    unwrap(
      apiClient.post<AccessTokenCreated>(`/admin/access-tokens/${id}/regenerate`),
    ),
  remove: (id: number) =>
    unwrap(apiClient.delete(`/admin/access-tokens/${id}`)),
};

// ===== Access Sessions (P-VIEWER 埋点) =====
export type AccessSessionStartResponse = {
  sessionId: number | null;
  startedAt: string | null;
  recorded: boolean;
};

/** 公共 API:开始一个 P-VIEWER 访问会话(无需 admin 鉴权)。
 *
 * 由 P-VIEWER 在素材加载成功后调用;后端按 B-1 自动跳过 OPEN 课件。
 * 失败/未记录 → recorded=false,前端不感知,继续浏览。
 */
export const AccessSessionAPI = {
  start: (params: { materialId: number; coursewareId: number | null }) => {
    const headers = tokenHashHeaders(params.coursewareId);
    return unwrap(
      apiClient.post<AccessSessionStartResponse>(
        "/public/access-sessions",
        { materialId: params.materialId },
        { headers },
      ),
    ).catch(() => ({ sessionId: null, startedAt: null, recorded: false }));
  },
  /** 离开 P-VIEWER 时调用,best-effort 失败不抛。
   *  优先 sendBeacon(切页/关页时最可靠),回退 fetch keepalive。
   */
  leave: (params: {
    sessionId: number;
    coursewareId: number | null;
    durationSeconds: number;
  }) => {
    const body = JSON.stringify({ durationSeconds: params.durationSeconds });
    const hash = params.coursewareId
      ? useTokenStore.getState().unlockedByCourseware[params.coursewareId] || ""
      : "";
    // 1) 优先 navigator.sendBeacon
    try {
      if (typeof navigator !== "undefined" && navigator.sendBeacon) {
        const url = `/api/public/access-sessions/${params.sessionId}/leave?X-Token-Hash=${encodeURIComponent(hash)}`;
        const blob = new Blob([body], { type: "application/json" });
        const ok = navigator.sendBeacon(url, blob);
        if (ok) return Promise.resolve({ ok: true });
      }
    } catch {
      // 退化
    }
    // 2) 回退 fetch keepalive
    return apiClient
      .post(
        `/public/access-sessions/${params.sessionId}/leave`,
        { durationSeconds: params.durationSeconds },
        {
          headers: tokenHashHeaders(params.coursewareId),
          // @ts-expect-error: keepalive 不是 axios 类型但浏览器 fetch 支持
          keepalive: true,
        },
      )
      .then(() => ({ ok: true }))
      .catch(() => ({ ok: false }));
  },
};

// ===== Access Token Usage (管理 API) =====
export type AccessSessionItem = {
  id: number;
  startedAt: string;
  endedAt: string | null;
  durationSeconds: number | null;
  clientLeave: boolean;
  coursewareId: number;
  coursewareTitle: string;
  materialId: number;
  materialName: string;
  materialType: string;
  ip: string | null;
  ua: string | null;
};
export type AccessSessionSummary = {
  totalDurationSeconds: number;
  sessionCount: number;
  coursewareCount: number;
  materialCount: number;
};
export type AccessSessionPaged = {
  page: number;
  size: number;
  total: number;
  summary: AccessSessionSummary;
  items: AccessSessionItem[];
};
export type MaterialUsageItem = {
  materialId: number;
  materialName: string;
  materialType: string;
  coursewareId: number;
  coursewareTitle: string;
  totalDurationSeconds: number;
  viewCount: number;
  lastViewedAt: string | null;
};
export type MaterialUsagePaged = {
  start: string;
  end: string;
  items: MaterialUsageItem[];
};

export const AccessTokenUsageAPI = {
  list: (
    id: number,
    params: {
      start: string;
      end: string;
      materialId?: number;
      coursewareId?: number;
      page?: number;
      size?: number;
    },
  ) =>
    unwrap(
      apiClient.get<AccessSessionPaged>(
        `/admin/access-tokens/${id}/access-sessions`,
        { params },
      ),
    ),
  materialSummary: (
    id: number,
    params: { start: string; end: string },
  ) =>
    unwrap(
      apiClient.get<MaterialUsagePaged>(
        `/admin/access-tokens/${id}/access-sessions/material-summary`,
        { params },
      ),
    ),
  /** 首屏概览:4 项聚合指标(总停留 / 次数 / 课件数 / 素材数),不含 items。 */
  summary: (id: number, params: { start: string; end: string }) =>
    unwrap(
      apiClient.get<AccessSessionSummary>(
        `/admin/access-tokens/${id}/access-sessions/summary`,
        { params },
      ),
    ),
};

// ===== Coursewares =====
export type CoursewareMaterialBrief = {
  id: number;
  name: string;
  type: string;
  sizeBytes: number;
  duration: string | null;
  /** 下载 URL。v1.2 起前台不再使用该字段（仅有后端 / 管理后台 / 调试使用），
   *  本字段声明为可选以便后续剥离时类型仍合法。 */
  downloadUrl?: string;
  streamUrl: string;
  /** 该素材在课件内的展示顺序（v1.5+）。同课件内 0..N-1 连续递增。 */
  sortOrder: number;
};

/** 公开素材单条查询返回结构（P-VIEWER 使用）。 */
export type PublicMaterialItem = {
  id: number;
  name: string;
  type: "VIDEO" | "PDF" | "PPT" | "ZIP";
  sizeBytes: number;
  duration: string | null;
  streamUrl: string;
  /** 下载 URL。v1.2 起 P-VIEWER 不再使用该字段（由 Viewer 透传时剥离），
   *  后端仍返回以保证 API 兼容性。本字段声明为可选以便剥离后类型仍合法。 */
  downloadUrl?: string;
  /** 前端是否可以直接内嵌预览(VIDEO/PDF 总是 true;PPT 仅当 PNG 已生成) */
  previewReady: boolean;
  /** PPT 专属:每页 PNG 预览图的 URL 列表(1-indexed) */
  imageUrls: string[];
  /** PPT 专属:图片总数(=imageUrls.length) */
  imageCount: number;
};
export type CoursewareItem = {
  id: number;
  title: string;
  author: string | null;
  categoryId: number;
  categoryName: string | null;
  description: string | null;
  accessMode: "OPEN" | "RESTRICTED";
  tagIds: number[];
  tagNames: string[];
  /** v1.5+：materialIds 与 materials 已按 sortOrder 升序返回（admin 设定顺序）。 */
  materialIds: number[];
  tokenIds: number[];
  createdAt: string | null;
  updatedAt: string | null;
  materials: CoursewareMaterialBrief[];
};
export type CoursewarePaged = {
  page: number;
  size: number;
  total: number;
  items: CoursewareItem[];
};

export const CoursewareAPI = {
  list: (
    params: {
      keyword?: string;
      categoryId?: number;
      accessMode?: string;
      page?: number;
      size?: number;
    } = {},
  ) => unwrap(apiClient.get<CoursewarePaged>("/admin/coursewares", { params })),
  get: (id: number) =>
    unwrap(apiClient.get<CoursewareItem>(`/admin/coursewares/${id}`)),
  create: (payload: {
    title: string;
    categoryId: number;
    author?: string;
    description?: string;
    accessMode: "OPEN" | "RESTRICTED";
    tagIds?: number[];
    materialIds?: number[];
    tokenIds?: number[];
  }) => unwrap(apiClient.post<CoursewareItem>("/admin/coursewares", payload)),
  update: (
    id: number,
    payload: Partial<{
      title: string;
      author: string;
      description: string;
      categoryId: number;
      accessMode: "OPEN" | "RESTRICTED";
      tagIds: number[];
      materialIds: number[];
      tokenIds: number[];
    }>,
  ) => unwrap(apiClient.put<CoursewareItem>(`/admin/coursewares/${id}`, payload)),
  /** v1.5+：专用排序接口。按 materialIds 数组顺序重写 sortOrder（0..N-1）。 */
  reorderMaterials: (coursewareId: number, materialIds: number[]) =>
    unwrap(
      apiClient.put<CoursewareItem>(
        `/admin/coursewares/${coursewareId}/materials/order`,
        { materialIds },
      ),
    ),
  remove: (id: number) =>
    unwrap(apiClient.delete(`/admin/coursewares/${id}`)),
};

// ===== Public =====
export const PublicCoursewareAPI = {
  search: (params: { q?: string; page?: number; size?: number } = {}) =>
    unwrap(
      apiClient.get<{
        items: CoursewareItem[];
        source?: "llm" | "keyword";
        total?: number;
        page: number;
        size: number;
      }>("/public/coursewares/search", { params }),
    ),
  get: (id: number) =>
    unwrap(
      apiClient.get<CoursewareItem>(`/public/coursewares/${id}`, {
        headers: tokenHashHeaders(id),
      }),
    ),
  unlock: (id: number, token: string) =>
    unwrap(
      apiClient.post<{ tokenHash: string; coursewareIds: number[] }>(
        `/public/coursewares/${id}/unlock`,
        { token },
      ),
    ),
  /** 公开素材单条查询（P-VIEWER 使用）。 */
  getMaterial: (id: number) => {
    // 从当前 store 读 coursewareId（由 Viewer 维护），取对应 tokenHash
    // 作为 X-Token-Hash 头，避免依赖 Set-Cookie 的写入时机。
    const coursewareId = useViewStore.getState().coursewareId;
    return unwrap(
      apiClient.get<PublicMaterialItem>(`/public/materials/${id}`, {
        headers: tokenHashHeaders(coursewareId),
      }),
    );
  },
};

export type ApiError = { code?: string; message?: string; status?: number };
