import axios, { AxiosError } from "axios";

/**
 * 统一 axios 客户端:
 * - baseURL 指向 /api(同源代理或反代)
 * - 自动附带 X-Request-Id
 * - 业务码非 ok 时抛错，供 React Query / Toast 统一兜底
 *
 * 注意:受限课件鉴权所需的 X-Token-Hash 头由调用方在
 * PublicCoursewareAPI.get / getMaterial 中显式传入，避免与 stream/file
 * 等 cookie-only 接口耦合。
 */
export const apiClient = axios.create({
  baseURL: "/api",
  withCredentials: true,
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const rid = crypto.randomUUID();
  config.headers["X-Request-Id"] = rid;
  return config;
});

apiClient.interceptors.response.use(
  (resp) => {
    const body = resp.data;
    if (body && typeof body === "object" && "code" in body) {
      if (body.code !== "ok") {
        const err = new Error(body.message || body.code) as Error & { code?: string; status?: number };
        err.code = body.code;
        err.status = resp.status;
        throw err;
      }
      // 业务成功:把 envelope.data 写回 resp.data,调用方 .then(r => r.data) 直接拿数据
      resp.data = body.data;
    }
    return resp;
  },
  (err: AxiosError<{ code?: string; message?: string }>) => {
    const body = err.response?.data;
    const code = body?.code || `http_${err.response?.status ?? "0"}`;
    const message = body?.message || err.message || "网络异常";
    const ex = new Error(message) as Error & { code?: string; status?: number };
    ex.code = code;
    ex.status = err.response?.status;
    return Promise.reject(ex);
  },
);

export type ApiEnvelope<T> = { code: string; message: string; data: T; requestId?: string };
