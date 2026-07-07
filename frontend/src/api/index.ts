/** 后端管理 API 包装:统一解 envelope,直接返回 data。 */
import { apiClient } from "./client";

const unwrap = <T>(p: Promise<{ data: T }>): Promise<T> => p.then((r) => r.data);

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
  type: "VIDEO" | "PDF" | "PPT";
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
        { headers: { "Content-Type": "multipart/form-data" } },
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

// ===== Coursewares =====
export type CoursewareMaterialBrief = {
  id: number;
  name: string;
  type: string;
  sizeBytes: number;
  duration: string | null;
  downloadUrl: string;
  streamUrl: string;
};

/** 公开素材单条查询返回结构（P-VIEWER 使用）。 */
export type PublicMaterialItem = {
  id: number;
  name: string;
  type: "VIDEO" | "PDF" | "PPT";
  sizeBytes: number;
  duration: string | null;
  streamUrl: string;
  downloadUrl: string;
  previewReady: boolean;
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
    unwrap(apiClient.get<CoursewareItem>(`/public/coursewares/${id}`)),
  unlock: (id: number, token: string) =>
    unwrap(
      apiClient.post<{ tokenHash: string; coursewareIds: number[] }>(
        `/public/coursewares/${id}/unlock`,
        { token },
      ),
    ),
  /** 公开素材单条查询（P-VIEWER 使用）。 */
  getMaterial: (id: number) =>
    unwrap(apiClient.get<PublicMaterialItem>(`/public/materials/${id}`)),
};

export type ApiError = { code?: string; message?: string; status?: number };