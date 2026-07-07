/**
 * P-HOME:前台首页(空态/极简入口)。
 *
 * - H1 + 搜索框 + 搜索按钮,主体内容居中并偏上对齐。
 * - 提交时设置 view=result + q=<关键词>,由 URL 同步。
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useViewStore } from "@/stores/view";

export function HomePage() {
  const go = useViewStore((s) => s.go);
  const router = useNavigate();
  const [q, setQ] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = q.trim();
    if (!trimmed) return;
    router(`/?view=result&q=${encodeURIComponent(trimmed)}`);
    go({ view: "result", q: trimmed });
  };

  return (
    <main className="min-h-screen flex flex-col items-center pt-[20vh] px-4">
      <h1 className="brand-title mb-3" data-testid="brand-title">
        Learning Hub
      </h1>
      <p className="text-slate-500 mb-8 text-sm">一句话找到你想学的课程</p>

      <form
        className="w-full max-w-2xl flex gap-2 shadow-sm"
        onSubmit={submit}
      >
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="请帮找一下项目管理相关的课程"
          data-testid="home-search-input"
          className="flex-1 border border-slate-300 rounded-l-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <button
          type="submit"
          data-testid="home-search-btn"
          className="bg-primary-600 hover:bg-primary-700 text-white px-6 py-3 rounded-r-lg font-medium"
        >
          搜索
        </button>
      </form>
    </main>
  );
}
