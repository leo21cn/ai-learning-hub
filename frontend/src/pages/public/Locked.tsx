/**
 * P-LOCKED:访问令牌解锁页。
 *
 * 通过 ?id=<coursewareId>&q=<returnQuery> 定位课件;接收明文 token 调
 * 用 /api/public/coursewares/{id}/unlock;成功后存储 tokenHash 并跳转
 * P-DETAIL。
 */
import { useEffect, useState } from "react";
import { useViewStore } from "@/stores/view";
import { useTokenStore } from "@/stores/token";
import { PublicCoursewareAPI } from "@/api";

export function LockedPage() {
  const id = useViewStore((s) => s.id);
  const q = useViewStore((s) => s.q);
  const go = useViewStore((s) => s.go);
  const unlock = useTokenStore((s) => s.unlock);

  const [tokenInput, setTokenInput] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (id == null) {
      go({ view: "home" });
    }
  }, [id, go]);

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setErr(null);
    setSubmitting(true);
    try {
      const res = await PublicCoursewareAPI.unlock(id, tokenInput.trim());
      unlock(id, res.tokenHash);
      setTokenInput("");
      go({ view: "detail" });
    } catch (e) {
      setErr((e as Error).message || "令牌无效");
    } finally {
      setSubmitting(false);
    }
  };

  if (id == null) return null;

  return (
    <main
      className="min-h-screen flex items-center justify-center px-4"
      data-testid="page-locked"
    >
      <div className="bg-white rounded-lg shadow-lg p-8 w-full max-w-md border border-amber-200">
        <div className="text-center mb-6">
          <div className="text-5xl mb-3">🔒</div>
          <h1 className="text-xl font-bold text-slate-800">该课件受访问限制</h1>
          <p className="text-sm text-slate-500 mt-2">
            请输入对应课件的访问令牌以查看内容
          </p>
        </div>

        <form onSubmit={handleUnlock} className="space-y-3">
          <label className="block">
            <span className="text-sm text-slate-700">访问令牌</span>
            <input
              autoFocus
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              data-testid="locked-token-input"
              placeholder="请输入令牌明文"
              className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2 font-mono"
            />
          </label>

          {err && (
            <div
              className="text-sm text-rose-600"
              data-testid="locked-error"
              role="alert"
            >
              {err}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !tokenInput.trim()}
            data-testid="locked-submit"
            className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-md font-medium"
          >
            {submitting ? "验证中..." : "解锁"}
          </button>
        </form>

        <div className="mt-6 flex justify-between text-xs">
          <button
            onClick={() => go({ view: "result", q })}
            className="text-slate-500 hover:underline"
          >
            ← 返回搜索
          </button>
          <button
            onClick={() => go({ view: "home" })}
            className="text-slate-500 hover:underline"
          >
            返回首页
          </button>
        </div>
      </div>
    </main>
  );
}
