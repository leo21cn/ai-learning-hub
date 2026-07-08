import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAdminStore } from "@/stores/admin";
import { Logo } from "@/components/Logo";

/**
 * A-LOGIN:管理员登录页。
 * - 输入 Admin Token,提交后端 /api/auth/admin 校验
 * - 当前阶段 1 仅占位;阶段 2 接入 issue_admin_jwt + Cookie
 */
export function LoginPage() {
  const navigate = useNavigate();
  const login = useAdminStore((s) => s.login);
  const loading = useAdminStore((s) => s.loading);
  const [token, setToken] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!token.trim()) {
      setErr("请输入 Token");
      return;
    }
    try {
      await login(token.trim());
      navigate("/admin/coursewares");
    } catch (ex) {
      const msg = ex instanceof Error ? ex.message : "登录失败";
      setErr(msg);
    }
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <div className="flex justify-center mb-1" data-testid="login-title">
          <Logo size={40} textClassName="text-slate-900" />
        </div>
        <p className="text-center text-slate-500 text-sm mb-6">管理员登录</p>
        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block">
            <span className="text-sm text-slate-700">Admin Token</span>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              data-testid="login-token-input"
              autoFocus
              className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="请输入管理令牌"
            />
          </label>
          {err && (
            <div data-testid="login-error" className="text-rose-600 text-sm bg-rose-50 rounded px-3 py-2">
              {err}
            </div>
          )}
          <button
            type="submit"
            disabled={loading}
            data-testid="login-submit"
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-md font-medium"
          >
            {loading ? "验证中..." : "登录"}
          </button>
        </form>
        <p className="text-center text-xs text-slate-400 mt-4">演示 Token: demo</p>
      </div>
    </main>
  );
}
