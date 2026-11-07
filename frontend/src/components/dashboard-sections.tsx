"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { ActivityEntry } from "@/lib/activity";
import type { Usage } from "@/lib/content";
import { timeAgo, type PlatformRow, type SeriesPoint, type Trend } from "@/lib/dashboard-metrics";

/* ---------- Small shared bits ---------- */

const icons: Record<string, string> = {
  send: "M22 2 11 13M22 2l-7 20-4-9-9-4z",
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  edit: "M4 20h4l11-11a2.1 2.1 0 0 0-4-4L4 16zM13.5 6.5l4 4",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  history: "M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2",
  star: "m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  arrow: "M5 12h14M13 6l6 6-6 6",
  up: "M12 19V5M5 12l7-7 7 7",
  down: "M12 5v14M19 12l-7 7-7-7",
  flat: "M5 12h14",
  chevron: "m9 6 6 6-6 6",
  alert: "M12 8v5M12 17h.01M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  bolt: "M13 2 4 14h7l-1 8 9-12h-7z",
  plus: "M12 5v14M5 12h14",
  user: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM19 8v6M22 11h-6",
  card: "M3 6h18v13H3zM3 10h18",
  sun: "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z",
  moon: "M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2z",
};

export function Icon({ name, size = 18 }: { name: keyof typeof icons | string; size?: number }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d={icons[name] ?? icons.chart} />
    </svg>
  );
}

export function Panel({ title, icon, action, children, className = "" }: { title: string; icon?: string; action?: { href: string; label: string }; children: ReactNode; className?: string }) {
  return (
    <section className={`db-panel ${className}`}>
      <header className="db-panel-head">
        <h2>{icon ? <span className="db-panel-icon"><Icon name={icon} size={17} /></span> : null}{title}</h2>
        {action ? <Link href={action.href} className="db-link">{action.label} <Icon name="arrow" size={13} /></Link> : null}
      </header>
      {children}
    </section>
  );
}

export function EmptyState({ message, href, cta }: { message: string; href?: string; cta?: string }) {
  return (
    <div className="db-empty">
      <p>{message}</p>
      {href && cta ? <Link href={href} className="db-link">{cta} <Icon name="arrow" size={13} /></Link> : null}
    </div>
  );
}

const PLATFORM_META: Record<string, { label: string; mark: string; cls: string }> = {
  facebook: { label: "Facebook", mark: "f", cls: "facebook" },
  instagram: { label: "Instagram", mark: "◎", cls: "instagram" },
  tiktok: { label: "TikTok", mark: "♪", cls: "tiktok" },
  youtube: { label: "YouTube", mark: "▶", cls: "youtube" },
};
export const platformMeta = (key: string) => PLATFORM_META[key] ?? { label: key, mark: key.slice(0, 1).toUpperCase(), cls: "other" };

export function PlatformBadge({ platform }: { platform: string }) {
  const meta = platformMeta(platform);
  return <span className={`db-platform ${meta.cls}`} aria-hidden="true">{meta.mark}</span>;
}

/* ---------- KPI card ---------- */

export function TrendBadge({ trend }: { trend: Trend }) {
  if (trend.direction === "none") return <span className="db-trend is-none">{trend.label}</span>;
  return (
    <span className={`db-trend is-${trend.direction}`}>
      <Icon name={trend.direction === "flat" ? "flat" : trend.direction} size={13} />
      {trend.label}
      <span className="sr-only"> compared with the previous period</span>
    </span>
  );
}

export function KpiCard({ href, icon, tone, label, value, trend, hint, loading }: {
  href: string; icon: string; tone: "brand" | "blue" | "green" | "orange"; label: string;
  value: number | string; trend?: Trend; hint?: string; loading?: boolean;
}) {
  return (
    <Link href={href} className="db-kpi">
      <span className={`db-kpi-icon tone-${tone}`}><Icon name={icon} size={22} /></span>
      <span className="db-kpi-body">
        <strong>{loading ? "—" : value}</strong>
        <small>{label}</small>
        {loading ? <span className="db-trend is-none">Loading…</span> : trend ? <TrendBadge trend={trend} /> : hint ? <span className="db-trend is-none">{hint}</span> : null}
      </span>
      <span className="db-kpi-chevron"><Icon name="chevron" size={16} /></span>
    </Link>
  );
}

/* ---------- Performance chart ---------- */

function smoothPath(points: Array<[number, number]>): string {
  if (points.length < 2) return "";
  let d = `M${points[0][0]},${points[0][1]}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2[0]},${p2[1]}`;
  }
  return d;
}

export function PerformanceChart({ series, loading }: { series: SeriesPoint[]; loading: boolean }) {
  const W = 640, H = 260, L = 48, R = 14, T = 14, B = 34;
  const rawMax = Math.max(1, ...series.flatMap((p) => [p.current, p.previous]));
  // Smallest "nice" step so four gridline intervals always cover the largest value.
  const need = rawMax / 4;
  let step = 1;
  for (let magnitude = 1; step < need; magnitude *= 10) {
    step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= need) ?? magnitude * 10;
  }
  const max = Math.max(step * 4, 4);
  const ticks = [0, 1, 2, 3, 4].map((i) => (max / 4) * i);
  const x = (i: number) => L + (i * (W - L - R)) / Math.max(1, series.length - 1);
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  const cur = series.map((p, i) => [x(i), y(p.current)] as [number, number]);
  const prev = series.map((p, i) => [x(i), y(p.previous)] as [number, number]);
  const hasData = series.some((p) => p.current > 0 || p.previous > 0);
  const curPath = smoothPath(cur);
  const area = curPath ? `${curPath} L${x(series.length - 1)},${y(0)} L${x(0)},${y(0)} Z` : "";
  const summary = hasData
    ? `Published posts per interval. ${series.map((p) => `${p.label}: ${p.current} this period, ${p.previous} last period`).join("; ")}.`
    : "No published posts in this period yet.";

  return (
    <div className="db-chart">
      <ul className="db-legend" aria-hidden="true"><li><i className="is-current" />This period</li><li><i className="is-previous" />Last period</li></ul>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary} preserveAspectRatio="xMidYMid meet">
        <defs><linearGradient id="db-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--brand)" stopOpacity=".22" /><stop offset="100%" stopColor="var(--brand)" stopOpacity="0" /></linearGradient></defs>
        {ticks.map((t) => (
          <g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="db-grid" /><text x={L - 8} y={y(t) + 4} textAnchor="end" className="db-axis">{Number.isInteger(t) ? t : t.toFixed(1)}</text></g>
        ))}
        {series.map((p, i) => <text key={p.label + i} x={x(i)} y={H - 10} textAnchor={i === series.length - 1 && i > 0 ? "end" : "middle"} className="db-axis">{p.label}</text>)}
        {hasData ? (
          <>
            <path d={area} fill="url(#db-area)" />
            <path d={smoothPath(prev)} className="db-line-prev" />
            <path d={curPath} className="db-line-cur" />
            {prev.map(([px, py], i) => <circle key={`p${i}`} cx={px} cy={py} r="3" className="db-dot-prev" />)}
            {cur.map(([cx, cy], i) => <circle key={`c${i}`} cx={cx} cy={cy} r="4.5" className="db-dot-cur"><title>{`${series[i].label}: ${series[i].current} published (last period ${series[i].previous})`}</title></circle>)}
          </>
        ) : null}
      </svg>
      {!hasData ? <div className="db-chart-empty">{loading ? "Loading performance…" : "Your posting activity will appear here once you publish your first post."}</div> : null}
    </div>
  );
}

/* ---------- Recent activity ---------- */

function activityTone(action: string): { icon: string; tone: string } {
  if (action.startsWith("scheduled_post") || action.startsWith("facebook_post") || action.startsWith("tiktok") || action.startsWith("youtube")) return { icon: "send", tone: "green" };
  if (action.startsWith("draft") || action.startsWith("content")) return { icon: "edit", tone: "blue" };
  if (action.startsWith("social_account")) return { icon: "link", tone: "brand" };
  if (action.startsWith("billing")) return { icon: "card", tone: "orange" };
  if (action.startsWith("organization") || action.startsWith("auth")) return { icon: "user", tone: "brand" };
  return { icon: "bolt", tone: "orange" };
}

export function ActivityList({ entries, loading }: { entries: ActivityEntry[]; loading: boolean }) {
  if (loading) return <EmptyState message="Loading recent activity…" />;
  if (!entries.length) return <EmptyState message="No activity yet. Actions in your workspace will show up here." />;
  return (
    <ul className="db-activity">
      {entries.map((entry) => {
        const { icon, tone } = activityTone(entry.action);
        return (
          <li key={entry.id}>
            <span className={`db-act-icon tone-${tone}`}><Icon name={icon} size={17} /></span>
            <span className="db-act-copy"><b>{entry.summary}</b><small>{entry.actor_name}</small></span>
            <time dateTime={entry.created_at}>{timeAgo(entry.created_at)}</time>
          </li>
        );
      })}
    </ul>
  );
}

/* ---------- Top platforms ---------- */

export function PlatformList({ rows, loading }: { rows: PlatformRow[]; loading: boolean }) {
  if (loading) return <EmptyState message="Loading platform performance…" />;
  if (!rows.length) return <EmptyState message="No platform data yet. Connect an account and publish to see how each channel performs." href="/social-accounts" cta="Connect an account" />;
  return (
    <ul className="db-platforms">
      {rows.slice(0, 4).map((row) => (
        <li key={row.platform}>
          <PlatformBadge platform={row.platform} />
          <span className="db-plat-name"><b>{platformMeta(row.platform).label}</b><small>{row.scheduled ? `${row.scheduled} scheduled` : "Nothing scheduled"}</small></span>
          <span className="db-plat-bar" aria-hidden="true"><i style={{ width: `${Math.max(row.share, row.published ? 6 : 0)}%` }} /></span>
          <span className="db-plat-num"><b>{row.published}</b><small>{row.published ? `${row.share}%` : "—"}</small></span>
        </li>
      ))}
    </ul>
  );
}

/* ---------- Plan usage ---------- */

export function PlanUsage({ usage, loading, failed }: { usage: Usage | null; loading: boolean; failed: boolean }) {
  if (loading) return <EmptyState message="Loading plan usage…" />;
  if (failed || !usage) return <EmptyState message="Plan usage isn’t available right now." href="/billing" cta="Open billing" />;
  const limited = usage.metrics.filter((m) => m.limit !== null && m.limit > 0);
  const ratios = limited.map((m) => Math.min(1, m.used / (m.limit as number)));
  const peak = ratios.length ? Math.max(...ratios) : 0;
  const percent = Math.round(peak * 100);
  const R = 52, C = 2 * Math.PI * R;
  return (
    <div className="db-usage">
      <div className="db-donut" role="img" aria-label={limited.length ? `${percent}% of your monthly limit used` : "No limits on this plan"}>
        <svg viewBox="0 0 140 140"><circle cx="70" cy="70" r={R} className="db-donut-track" /><circle cx="70" cy="70" r={R} className="db-donut-value" strokeDasharray={`${C * peak} ${C}`} transform="rotate(-90 70 70)" /></svg>
        <span><b>{limited.length ? `${percent}%` : "∞"}</b><small>{limited.length ? "Used" : "Unlimited"}</small></span>
      </div>
      <div className="db-usage-copy">
        <p><strong>{usage.plan_name} plan</strong>{limited.length ? ` — you’ve used ${percent}% of your most-used monthly limit.` : " — no monthly limits apply."}</p>
        <ul>
          {limited.slice(0, 4).map((m) => (
            <li key={m.metric}><span>{m.label.charAt(0).toUpperCase() + m.label.slice(1)}</span><b>{m.used}/{m.limit}</b><i aria-hidden="true"><em style={{ width: `${Math.min(100, ((m.used / (m.limit as number)) * 100))}%` }} /></i></li>
          ))}
        </ul>
        <Link href="/billing" className="db-btn">View plan details</Link>
      </div>
    </div>
  );
}
