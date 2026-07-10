/** 访问令牌 · 访问记录页面(管理后台)
 *
 * 展示某 token 在时间段内的访问台账 + 按素材聚合的总停留时长。
 * 默认时间段:近 7 天(今天 vs 7 天前)。
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AccessTokenUsageAPI,
  type AccessSessionItem,
  type AccessSessionPaged,
  type AccessSessionSummary,
  type MaterialUsageItem,
  type MaterialUsagePaged,
} from "@/api";
import { toast } from "@/stores/toast";

type Tab = "summary" | "ledger";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
function monthStartISO(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1)
    .toISOString()
    .slice(0, 10);
}

function daysAgoISO(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function formatDateTime(s: string | null | undefined): string {
  if (!s) return "-";
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "-";
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${sec
      .toString()
      .padStart(2, "0")}`;
  }
  return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
}

export function AccessTokenUsagePage() {
  const { id } = useParams<{ id: string }>();
  const tokenId = Number(id);

  // 时间段默认近 7 天
  const [start, setStart] = useState<string>(daysAgoISO(6));
  const [end, setEnd] = useState<string>(todayISO());

  // 概览 + summary
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [materialSummary, setMaterialSummary] = useState<MaterialUsagePaged | null>(
    null,
  );
  const [ledger, setLedger] = useState<AccessSessionPaged | null>(null);
  // 首屏概览(4 项指标,独立于 tab 状态):进入页面即拉取。
  const [overviewSummary, setOverviewSummary] = useState<AccessSessionSummary | null>(
    null,
  );

  // tab
  const [tab, setTab] = useState<Tab>("summary");

  // 明细分页(SIZE=15/页,与项目 Materials/Coursewares 列表一致)
  const [page, setPage] = useState(1);
  const SIZE = 15;

  const loadOverview = useCallback(async () => {
    if (!Number.isFinite(tokenId)) return;
    try {
      const data = await AccessTokenUsageAPI.summary(tokenId, { start, end });
      setOverviewSummary(data);
    } catch (e) {
      toast((e as Error).message || "加载概览失败", "error");
    }
  }, [tokenId, start, end]);

  const loadSummary = useCallback(async () => {
    if (!Number.isFinite(tokenId)) return;
    setSummaryLoading(true);
    try {
      const data = await AccessTokenUsageAPI.materialSummary(tokenId, {
        start,
        end,
      });
      setMaterialSummary(data);
    } catch (e) {
      toast((e as Error).message || "加载素材汇总失败", "error");
    } finally {
      setSummaryLoading(false);
    }
  }, [tokenId, start, end]);

  const loadLedger = useCallback(async () => {
    if (!Number.isFinite(tokenId)) return;
    setSummaryLoading(true);
    try {
      const data = await AccessTokenUsageAPI.list(tokenId, {
        start,
        end,
        page,
        size: SIZE,
      });
      setLedger(data);
    } catch (e) {
      toast((e as Error).message || "加载访问台账失败", "error");
    } finally {
      setSummaryLoading(false);
    }
  }, [tokenId, start, end, page]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    if (tab === "ledger") {
      setPage(1);
      loadLedger();
    }
  }, [tab, loadLedger]);

  useEffect(() => {
    if (tab === "ledger") loadLedger();
  }, [page, tab, loadLedger]);

  const applyQuickRange = (n: number) => {
    setStart(daysAgoISO(n - 1));
    setEnd(todayISO());
    setPage(1);
  };

  /** Spec §4.2:快捷「本月」→ start = 本月 1 号,end = 今天 */
  const applyCurrentMonth = () => {
    setStart(monthStartISO());
    setEnd(todayISO());
    setPage(1);
  };

  const overview = useMemo(() => {
    // 优先使用首屏 summary 端点(独立于 tab 拉取),回落到台账 summary / 素材汇总。
    if (overviewSummary) {
      return {
        totalDurationSeconds: overviewSummary.totalDurationSeconds,
        sessionCount: overviewSummary.sessionCount,
        coursewareCount: overviewSummary.coursewareCount,
        materialCount: overviewSummary.materialCount,
      };
    }
    return ledger?.summary || materialSummary?.items
      ? {
          totalDurationSeconds:
            ledger?.summary?.totalDurationSeconds ??
            materialSummary?.items.reduce(
              (a: number, b: MaterialUsageItem) => a + b.totalDurationSeconds,
              0,
            ) ??
            0,
          sessionCount: ledger?.summary?.sessionCount ?? null,
          coursewareCount: ledger?.summary?.coursewareCount ?? null,
          materialCount:
            ledger?.summary?.materialCount ?? materialSummary?.items.length ?? 0,
        }
      : null;
  }, [overviewSummary, ledger, materialSummary]);

  return (
    <div className="max-w-6xl mx-auto">
      <header className="mb-6">
        <Link
          to="/admin/access-tokens"
          className="text-sm text-primary-600 hover:underline"
          data-testid="usage-back-link"
        >
          ← 返回访问令牌
        </Link>
        <h1 className="text-2xl font-bold text-slate-800 mt-2">
          访问记录
        </h1>
      </header>

      {/* 筛选区 */}
      <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-4 mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">起</label>
            <input
              type="date"
              value={start}
              max={end}
              onChange={(e) => {
                setStart(e.target.value);
                setPage(1);
              }}
              data-testid="usage-start"
              className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">止</label>
            <input
              type="date"
              value={end}
              min={start}
              max={todayISO()}
              onChange={(e) => {
                setEnd(e.target.value);
                setPage(1);
              }}
              data-testid="usage-end"
              className="border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex gap-1 ml-auto">
            <button
              onClick={() => applyQuickRange(7)}
              data-testid="usage-quick-7d"
              className="px-2 py-1 text-xs border border-slate-300 rounded hover:bg-slate-50"
            >
              近 7 天
            </button>
            <button
              onClick={() => applyQuickRange(30)}
              data-testid="usage-quick-30d"
              className="px-2 py-1 text-xs border border-slate-300 rounded hover:bg-slate-50"
            >
              近 30 天
            </button>
            <button
              onClick={applyCurrentMonth}
              data-testid="usage-quick-month"
              className="px-2 py-1 text-xs border border-slate-300 rounded hover:bg-slate-50"
            >
              本月
            </button>
          </div>
        </div>
      </div>

      {/* 概览卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <OverviewCard
          label="总停留时长"
          value={formatDuration(overview?.totalDurationSeconds ?? 0)}
          testid="usage-card-total-duration"
        />
        <OverviewCard
          label="总访问次数"
          value={overview?.sessionCount != null ? String(overview.sessionCount) : "-"}
          testid="usage-card-session-count"
        />
        <OverviewCard
          label="覆盖课件"
          value={overview?.coursewareCount != null ? String(overview.coursewareCount) : "-"}
          testid="usage-card-courseware-count"
        />
        <OverviewCard
          label="覆盖素材"
          value={String(overview?.materialCount ?? 0)}
          testid="usage-card-material-count"
        />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-4">
        <button
          onClick={() => setTab("summary")}
          data-testid="usage-tab-summary"
          className={`px-4 py-2 text-sm border-b-2 ${
            tab === "summary"
              ? "border-primary-600 text-primary-700 font-medium"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          按素材汇总
        </button>
        <button
          onClick={() => setTab("ledger")}
          data-testid="usage-tab-ledger"
          className={`px-4 py-2 text-sm border-b-2 ${
            tab === "ledger"
              ? "border-primary-600 text-primary-700 font-medium"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          访问台账
        </button>
      </div>

      {tab === "summary" && (
        <SummaryTable
          loading={summaryLoading}
          items={materialSummary?.items || []}
        />
      )}

      {tab === "ledger" && (
        <LedgerTable
          loading={summaryLoading}
          paged={ledger}
          page={page}
          size={SIZE}
          onPage={setPage}
        />
      )}
    </div>
  );
}

function OverviewCard({
  label,
  value,
  testid,
}: {
  label: string;
  value: string;
  testid: string;
}) {
  return (
    <div
      className="bg-white rounded-lg shadow-sm border border-slate-200 p-4"
      data-testid={testid}
    >
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-2xl font-bold text-slate-800 mt-1">{value}</div>
    </div>
  );
}

function SummaryTable({
  loading,
  items,
}: {
  loading: boolean;
  items: MaterialUsageItem[];
}) {
  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500">
        加载中…
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div
        className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500"
        data-testid="usage-summary-empty"
      >
        该时间段内无访问记录
      </div>
    );
  }
  return (
    <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600 text-left">
          <tr>
            <th className="px-4 py-2">素材名</th>
            <th className="px-4 py-2">类型</th>
            <th className="px-4 py-2">所属课件</th>
            <th className="px-4 py-2 text-right">访问次数</th>
            <th className="px-4 py-2 text-right">总停留</th>
            <th className="px-4 py-2">最近访问</th>
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr
              key={m.materialId}
              data-testid={`usage-summary-row-${m.materialId}`}
              className="border-t border-slate-100"
            >
              <td className="px-4 py-2 font-medium text-slate-800">
                {m.materialName}
              </td>
              <td className="px-4 py-2 text-slate-600">{m.materialType}</td>
              <td className="px-4 py-2 text-slate-600">
                {m.coursewareTitle}
              </td>
              <td className="px-4 py-2 text-right text-slate-700">
                {m.viewCount}
              </td>
              <td
                className="px-4 py-2 text-right text-slate-700 font-mono"
                data-testid={`usage-summary-duration-${m.materialId}`}
              >
                {formatDuration(m.totalDurationSeconds)}
              </td>
              <td className="px-4 py-2 text-slate-500 text-xs">
                {formatDateTime(m.lastViewedAt)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LedgerTable({
  loading,
  paged,
  page,
  size,
  onPage,
}: {
  loading: boolean;
  paged: AccessSessionPaged | null;
  page: number;
  size: number;
  onPage: (p: number) => void;
}) {
  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500">
        加载中…
      </div>
    );
  }
  const items = paged?.items || [];
  const total = paged?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
      {items.length === 0 ? (
        <div
          className="p-8 text-center text-slate-500"
          data-testid="usage-ledger-empty"
        >
          该时间段内无访问记录
        </div>
      ) : (
        <>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-left">
              <tr>
                <th className="px-4 py-2">开始时间</th>
                <th className="px-4 py-2">结束时间</th>
                <th className="px-4 py-2 text-right">停留</th>
                <th className="px-4 py-2">课件</th>
                <th className="px-4 py-2">素材</th>
                <th className="px-4 py-2">类型</th>
                <th className="px-4 py-2">IP</th>
                <th className="px-4 py-2">状态</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s: AccessSessionItem) => (
                <tr
                  key={s.id}
                  data-testid={`usage-ledger-row-${s.id}`}
                  className="border-t border-slate-100"
                >
                  <td className="px-4 py-2 text-slate-600 text-xs">
                    {formatDateTime(s.startedAt)}
                  </td>
                  <td className="px-4 py-2 text-slate-600 text-xs">
                    {s.endedAt ? formatDateTime(s.endedAt) : "进行中"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-slate-700">
                    {formatDuration(s.durationSeconds)}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    {s.coursewareTitle}
                  </td>
                  <td className="px-4 py-2 text-slate-700">{s.materialName}</td>
                  <td className="px-4 py-2 text-slate-500 text-xs">
                    {s.materialType}
                  </td>
                  <td className="px-4 py-2 text-slate-500 text-xs">{s.ip || "-"}</td>
                  <td className="px-4 py-2 text-xs">
                    {s.clientLeave ? (
                      <span className="text-slate-500">已结束</span>
                    ) : (
                      <span className="text-amber-600">进行中</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 text-sm">
            <span className="text-slate-500">
              共 {total} 条 / 第 {page} / {totalPages} 页
            </span>
            <div className="space-x-2">
              <button
                onClick={() => onPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                data-testid="usage-ledger-prev"
                className="px-3 py-1 border border-slate-300 rounded disabled:opacity-50 hover:bg-slate-50"
              >
                上一页
              </button>
              <button
                onClick={() => onPage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                data-testid="usage-ledger-next"
                className="px-3 py-1 border border-slate-300 rounded disabled:opacity-50 hover:bg-slate-50"
              >
                下一页
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
