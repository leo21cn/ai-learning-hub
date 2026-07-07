/**
 * SPA 入口:将前台 4 个 UI 实体合并到单 URL(`/`),由 store/view 的
 * `view` 参数路由; admin/* 仍走独立子路由。
 */
import { useEffect } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import {
  useViewStore,
  hydrateViewFromUrl,
  syncViewFromUrl,
  bindViewToPopState,
} from "@/stores/view";
import { hydrateTokenStore } from "@/stores/token";
import { useAdminStore } from "@/stores/admin";
import { ToastViewport } from "@/components/Toast";

import { HomePage } from "@/pages/public/Home";
import { ResultPage } from "@/pages/public/Result";
import { LockedPage } from "@/pages/public/Locked";
import { DetailPage } from "@/pages/public/Detail";
import { Viewer } from "@/pages/public/Viewer";
import { LoginPage } from "@/pages/admin/Login";
import { CategoriesPage } from "@/pages/admin/Categories";
import { TagsPage } from "@/pages/admin/Tags";
import { MaterialsPage } from "@/pages/admin/Materials";
import { AccessTokensPage } from "@/pages/admin/AccessTokens";
import { CoursewaresPage } from "@/pages/admin/Coursewares";
import { AdminLayout } from "@/layouts/AdminLayout";

function AdminGuard({ children }: { children: React.ReactNode }) {
  const session = useAdminStore((s) => s.session);
  if (!session) return <Navigate to="/admin" replace />;
  return <>{children}</>;
}

/**
 * 前台 SPA 壳:`/` 单 URL 内通过 store/view 切换页面。
 */
function PublicShell() {
  const view = useViewStore((s) => s.view);
  const location = typeof window !== "undefined" ? window.location : null;

  useEffect(() => {
    // 每次 pathname/search 变化都重新同步 store(浏览器内 SPA 导航)
    if (location) syncViewFromUrl();
  }, [location?.search, location?.pathname]);

  return (
    <div className="min-h-screen">
      {view === "home" && <HomePage />}
      {view === "result" && <ResultPage />}
      {view === "locked" && <LockedPage />}
      {view === "detail" && <DetailPage />}
      {view === "viewer" && <Viewer />}
    </div>
  );
}

export default function App() {
  const restore = useAdminStore((s) => s.restore);

  useEffect(() => {
    hydrateViewFromUrl();
    hydrateTokenStore();
    const unbind = bindViewToPopState();
    return unbind;
  }, []);

  useEffect(() => {
    restore();
  }, [restore]);

  return (
    <>
      <ToastViewport />
      <Routes>
        <Route path="/" element={<PublicShell />} />
        <Route path="/admin" element={<LoginPage />} />
        <Route
          element={
            <AdminGuard>
              <AdminLayout />
            </AdminGuard>
          }
        >
          <Route path="/admin/categories" element={<CategoriesPage />} />
          <Route path="/admin/tags" element={<TagsPage />} />
          <Route path="/admin/materials" element={<MaterialsPage />} />
          <Route path="/admin/access-tokens" element={<AccessTokensPage />} />
          <Route path="/admin/coursewares" element={<CoursewaresPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
