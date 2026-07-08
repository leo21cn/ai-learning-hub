/**
 * P-RESULT:关键词搜索结果。
 *
 * 按 query ?q= 调用 /api/public/coursewares/search 列出命中课件。
 * RESTRICTED 课件仍可出现在结果中(参见 03 §F-019a);点击进入 P-LOCKED。
 */
import { useEffect, useState } from "react";
import { useViewStore } from "@/stores/view";
import {
  PublicCoursewareAPI,
  type CoursewareItem,
} from "@/api";

export function ResultPage() {
  const q = useViewStore((s) => s.q);
  const go = useViewStore((s) => s.go);
  const [items, setItems] = useState<CoursewareItem[]>([]);
  // 初始为 null:请求未完成时,源未确定,避免先“降级中”闪一下。
  // 拿到响应后再 setSource(res.source ?? "keyword")。
  const [source, setSource] = useState<"llm" | "keyword" | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    setErr(null);
    PublicCoursewareAPI.search({ q, page: 1, size: 50 })
      .then((res) => {
        if (cancel) return;
        setItems(res.items ?? []);
        setSource(res.source ?? "keyword");
      })
      .catch((e: Error) => {
        if (cancel) return;
        setErr(e.message || "搜索失败");
      })
      .finally(() => !cancel && setLoading(false));
    return () => {
      cancel = true;
    };
  }, [q]);

  return (
    <main className="max-w-4xl mx-auto py-10 px-4" data-testid="page-result">
      <header className="mb-6">
        <button
          onClick={() => go({ view: "home" })}
          className="text-sm text-slate-500 hover:underline mb-3"
        >
          ← 返回首页
        </button>
        <h1 className="text-2xl font-bold text-slate-800">
          搜索结果 <span className="text-base text-slate-500">"{q}"</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          共 {items.length} 条结果
          {source === "llm" && (
            <span
              className="ml-2 px-2 py-0.5 text-xs rounded bg-primary-100 text-primary-700"
              data-testid="source-llm"
            >
              AI 智能搜索
            </span>
          )}
          {source === "keyword" && (
            <span
              className="ml-2 px-2 py-0.5 text-xs rounded bg-amber-100 text-amber-700"
              title="LLM 不可用,已自动降级到关键词搜索"
              data-testid="source-keyword"
            >
              AI 智能搜索
              <span className="ml-1 text-amber-500">· 降级中</span>
            </span>
          )}
        </p>
      </header>

      {loading && (
        <div className="text-center text-slate-500 py-12">加载中…</div>
      )}
      {err && (
        <div className="text-center text-rose-600 py-12" data-testid="result-err">
          {err}
        </div>
      )}
      {!loading && !err && items.length === 0 && (
        <div
          className="text-center text-slate-500 py-16"
          data-testid="result-empty"
        >
          没有匹配的课件,试试更短的关键词
        </div>
      )}

      <ul className="space-y-3">
        {items.map((cw) => (
          <li
            key={cw.id}
            data-testid={`result-item-${cw.id}`}
            className="bg-white border border-slate-200 rounded-lg p-4 hover:shadow-sm transition cursor-pointer"
            onClick={() =>
              go({
                view: cw.accessMode === "RESTRICTED" ? "locked" : "detail",
                id: cw.id,
              })
            }
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <h2 className="font-semibold text-slate-800">{cw.title}</h2>
                {cw.author && (
                  <p className="text-xs text-slate-500 mt-0.5">作者: {cw.author}</p>
                )}
                {cw.description && (
                  <p className="text-sm text-slate-600 mt-1 line-clamp-2">
                    {cw.description}
                  </p>
                )}
                {cw.tagNames?.length > 0 && (
                  <div className="mt-2 flex gap-1 flex-wrap">
                    {cw.tagNames.map((t, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-600"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <span
                className={`shrink-0 px-2 py-0.5 text-xs rounded ${
                  cw.accessMode === "RESTRICTED"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-emerald-100 text-emerald-700"
                }`}
              >
                {cw.accessMode === "RESTRICTED" ? "受限" : "开放"}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
