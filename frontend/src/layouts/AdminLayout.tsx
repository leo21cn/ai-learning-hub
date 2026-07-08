import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAdminStore } from "@/stores/admin";
import { ToastViewport } from "@/components/Toast";
import { Logo } from "@/components/Logo";

const NAV = [
  { to: "/admin/coursewares", label: "课件管理" },
  { to: "/admin/categories", label: "分类管理" },
  { to: "/admin/tags", label: "标签管理" },
  { to: "/admin/materials", label: "素材管理" },
  { to: "/admin/access-tokens", label: "访问令牌" },
];

export function AdminLayout() {
  const logout = useAdminStore((s) => s.logout);
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/admin");
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center gap-6">
        <Logo size={28} textClassName="text-slate-800" />
        <span className="text-sm text-slate-500">· 管理后台</span>
        <nav className="flex gap-1 text-sm" data-testid="admin-nav">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={`nav-${n.to.split("/").pop()}`}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded ${
                  isActive ? "bg-primary-50 text-primary-700" : "text-slate-600 hover:bg-slate-50"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <button
            onClick={onLogout}
            data-testid="admin-logout"
            className="px-3 py-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-50"
          >
            退出登录
          </button>
        </div>
      </header>
      <main className="flex-1 bg-slate-50 p-6">
        <Outlet />
      </main>
      <ToastViewport />
    </div>
  );
}
