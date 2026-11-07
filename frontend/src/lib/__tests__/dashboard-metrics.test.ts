import { describe, expect, it } from "vitest";
import { buildSeries, computeStats, describeTrend, platformBreakdown } from "../dashboard-metrics";
import type { CalendarItem } from "../social";

const NOW = new Date("2026-11-06T12:00:00Z").getTime();
const day = (n: number) => new Date(NOW - n * 86_400_000).toISOString();
const post = (over: Partial<CalendarItem>): CalendarItem => ({ id: "1", kind: "post", platform: "facebook", title: "t", content: "c", status: "published", created_at: day(1), scheduled_at: null, ...over });

describe("describeTrend", () => {
  it("shows no data when both periods are empty", () => expect(describeTrend(0, 0)).toEqual({ direction: "none", label: "No data yet" }));
  it("marks growth from zero as new", () => expect(describeTrend(3, 0)).toEqual({ direction: "up", label: "New" }));
  it("computes decreases", () => expect(describeTrend(5, 10)).toEqual({ direction: "down", label: "50%" }));
});

describe("computeStats", () => {
  it("compares published posts to the previous period", () => {
    const items = [post({ created_at: day(2) }), post({ id: "2", created_at: day(3) }), post({ id: "3", created_at: day(40) })];
    const stats = computeStats(items, [], 2, 30, NOW);
    expect(stats.published).toEqual({ current: 2, previous: 1 });
    expect(stats.accounts.total).toBe(2);
  });
  it("returns zeros for an empty workspace", () => {
    const stats = computeStats([], [], 0, 30, NOW);
    expect(stats.published.current + stats.scheduled.current + stats.drafts.current + stats.failed).toBe(0);
  });
});

describe("series and platforms", () => {
  it("buckets published posts and ranks platforms", () => {
    const items = [post({ created_at: day(2) }), post({ id: "2", platform: "tiktok", created_at: day(2) }), post({ id: "3", created_at: day(5) })];
    expect(buildSeries(items, 30, NOW).reduce((s, p) => s + p.current, 0)).toBe(3);
    expect(platformBreakdown(items, 30, NOW)[0]).toMatchObject({ platform: "facebook", published: 2 });
  });
});
