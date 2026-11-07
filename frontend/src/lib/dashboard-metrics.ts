import type { CalendarItem } from "@/lib/social";
import type { Draft } from "@/lib/content";

export type RangeDays = 7 | 30 | 90;
export const RANGE_OPTIONS: ReadonlyArray<{ value: RangeDays; label: string }> = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
];

const DAY = 86_400_000;
const PUBLISHED = ["published", "completed", "succeeded", "success", "processed", "live"];
const FAILED = ["failed", "error", "rejected"];

export const isPublished = (item: CalendarItem) => PUBLISHED.includes(item.status.toLowerCase());
export const isFailed = (item: CalendarItem) => FAILED.includes(item.status.toLowerCase());
const isPost = (item: CalendarItem) => item.kind !== "draft";
const stamp = (item: CalendarItem) => new Date(item.scheduled_at || item.created_at).getTime();

/** Percentage change vs the previous period. `null` means there is nothing to compare yet. */
export function percentChange(current: number, previous: number): number | null {
  if (previous <= 0) return null;
  return Math.round(((current - previous) / previous) * 100);
}

export type Trend = { direction: "up" | "down" | "flat" | "none"; label: string };

/** Turns a change into an arrow + label. Shows "New" when growth from zero cannot be a percentage. */
export function describeTrend(current: number, previous: number): Trend {
  if (current === 0 && previous === 0) return { direction: "none", label: "No data yet" };
  if (previous === 0) return { direction: "up", label: "New" };
  const change = percentChange(current, previous) ?? 0;
  if (change === 0) return { direction: "flat", label: "0%" };
  return { direction: change > 0 ? "up" : "down", label: `${Math.abs(change)}%` };
}

function inWindow(time: number, start: number, end: number) {
  return time >= start && time < end;
}

export type DashboardStats = {
  published: { current: number; previous: number };
  scheduled: { current: number; previous: number };
  drafts: { current: number; previous: number };
  accounts: { total: number };
  failed: number;
};

export function computeStats(items: CalendarItem[], drafts: Draft[], accountCount: number, days: RangeDays, now = Date.now()): DashboardStats {
  const start = now - days * DAY;
  const prevStart = start - days * DAY;
  const posts = items.filter(isPost);
  const publishedItems = posts.filter(isPublished);
  const upcomingItems = posts.filter((item) => !isPublished(item) && !isFailed(item) && Boolean(item.scheduled_at));
  const count = (list: Array<{ t: number }>, a: number, b: number) => list.filter((x) => inWindow(x.t, a, b)).length;
  const pub = publishedItems.map((item) => ({ t: stamp(item) }));
  const sched = upcomingItems.map((item) => ({ t: new Date(item.created_at).getTime() }));
  const dr = drafts.filter((d) => d.status === "draft").map((d) => ({ t: new Date(d.created_at).getTime() }));
  return {
    published: { current: count(pub, start, now + 1), previous: count(pub, prevStart, start) },
    scheduled: { current: upcomingItems.length, previous: count(sched, prevStart, start) },
    drafts: { current: dr.filter((x) => x.t >= start).length, previous: count(dr, prevStart, start) },
    accounts: { total: accountCount },
    failed: posts.filter(isFailed).length,
  };
}

export type SeriesPoint = { label: string; current: number; previous: number };

/** Buckets published posts into ~5-7 evenly spaced points for "this period" vs "last period". */
export function buildSeries(items: CalendarItem[], days: RangeDays, now = Date.now()): SeriesPoint[] {
  const buckets = days === 7 ? 7 : days === 30 ? 6 : 6;
  const size = (days * DAY) / buckets;
  const start = now - days * DAY;
  const published = items.filter((item) => isPost(item) && isPublished(item)).map(stamp);
  return Array.from({ length: buckets }, (_, index) => {
    const a = start + index * size;
    const b = a + size;
    const label = new Date(a).toLocaleDateString([], { month: "short", day: "numeric" });
    return {
      label,
      current: published.filter((t) => inWindow(t, a, b)).length,
      previous: published.filter((t) => inWindow(t, a - days * DAY, b - days * DAY)).length,
    };
  });
}

export type PlatformRow = { platform: string; published: number; scheduled: number; share: number };

export function platformBreakdown(items: CalendarItem[], days: RangeDays, now = Date.now()): PlatformRow[] {
  const start = now - days * DAY;
  const map = new Map<string, { published: number; scheduled: number }>();
  for (const item of items.filter(isPost)) {
    if (!item.platform || item.platform === "all") continue;
    const row = map.get(item.platform) ?? { published: 0, scheduled: 0 };
    if (isPublished(item) && stamp(item) >= start) row.published += 1;
    else if (!isPublished(item) && !isFailed(item) && item.scheduled_at) row.scheduled += 1;
    map.set(item.platform, row);
  }
  const rows = [...map.entries()].map(([platform, v]) => ({ platform, ...v, share: 0 }));
  const total = rows.reduce((sum, row) => sum + row.published, 0);
  rows.forEach((row) => { row.share = total ? Math.round((row.published / total) * 100) : 0; });
  return rows.sort((a, b) => b.published - a.published || b.scheduled - a.scheduled);
}

export function timeAgo(iso: string, now = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const daysAgo = Math.round(hours / 24);
  return daysAgo < 30 ? `${daysAgo}d ago` : new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}
