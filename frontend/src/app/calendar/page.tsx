"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, getStoredOrganization } from "@/lib/auth";
import { fetchCalendar, type CalendarItem } from "@/lib/social";

type CalendarView = "month" | "week" | "agenda";
const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());
const addDays = (date: Date, amount: number) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + amount);
const eventDate = (item: CalendarItem) => new Date(item.scheduled_at || item.created_at);
const formatTime = (date: Date) => date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

function EventCard({ item, compact = false }: { item: CalendarItem; compact?: boolean }) {
  const when = eventDate(item);
  return (
    <article className={`rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] ${compact ? "p-2" : "p-4"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wide text-[var(--color-brand)]">{item.platform} · {item.kind}</span>
        <span className="rounded-full bg-[var(--color-page)] px-2.5 py-1 text-[10px] font-semibold capitalize">{item.status}</span>
      </div>
      <h3 className={`mt-1 font-bold ${compact ? "line-clamp-2 text-xs" : "text-sm"}`}>{item.title}</h3>
      {!compact && <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--color-text-muted)]">{item.content}</p>}
      <p className="mt-2 text-[11px] text-[var(--color-text-muted)]">
        {item.scheduled_at ? `Scheduled · ${formatTime(when)}` : `Created · ${formatTime(when)}`}
      </p>
    </article>
  );
}

export default function CalendarPage() {
  const router = useRouter();
  const [items, setItems] = useState<CalendarItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<CalendarView>("month");
  const [selectedDate, setSelectedDate] = useState(() => startOfDay(new Date()));

  useEffect(() => {
    const token = getAccessToken();
    const organization = getStoredOrganization();
    if (!token || !organization) {
      router.replace("/login");
      return;
    }
    void fetchCalendar(token, organization.id)
      .then(setItems)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Calendar could not be loaded."))
      .finally(() => setLoading(false));
  }, [router]);

  const monthStart = useMemo(() => new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1), [selectedDate]);
  const gridStart = useMemo(() => addDays(monthStart, -monthStart.getDay()), [monthStart]);
  const weekStart = useMemo(() => addDays(selectedDate, -selectedDate.getDay()), [selectedDate]);
  const visibleStart = view === "week" ? weekStart : view === "agenda" ? startOfDay(selectedDate) : gridStart;
  const visibleEnd = view === "week" ? addDays(weekStart, 7) : view === "agenda" ? addDays(selectedDate, 30) : addDays(gridStart, 42);

  const eventsByDay = useMemo(() => {
    const grouped = new Map<string, CalendarItem[]>();
    for (const item of items) {
      const key = dateKey(eventDate(item));
      grouped.set(key, [...(grouped.get(key) || []), item]);
    }
    for (const events of grouped.values()) events.sort((a, b) => eventDate(a).getTime() - eventDate(b).getTime());
    return grouped;
  }, [items]);

  const visibleItems = useMemo(() => items
    .filter((item) => eventDate(item) >= visibleStart && eventDate(item) < visibleEnd)
    .sort((a, b) => eventDate(a).getTime() - eventDate(b).getTime()), [items, visibleStart, visibleEnd]);

  const navigate = useCallback((direction: number) => {
    if (view === "agenda") setSelectedDate((current) => addDays(current, direction * 30));
    else if (view === "week") setSelectedDate((current) => addDays(current, direction * 7));
    else setSelectedDate((current) => new Date(current.getFullYear(), current.getMonth() + direction, 1));
  }, [view]);

  const heading = view === "agenda"
    ? `${selectedDate.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })} – ${addDays(selectedDate, 29).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`
    : view === "week"
      ? `${weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${addDays(weekStart, 6).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`
      : selectedDate.toLocaleDateString(undefined, { month: "long", year: "numeric" });

  const days = view === "week"
    ? Array.from({ length: 7 }, (_, index) => addDays(weekStart, index))
    : Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));

  return (
    <main className="min-h-screen bg-[var(--color-page)] px-3 py-6 text-[var(--color-text)] sm:px-6 sm:py-8">
      <div className="mx-auto max-w-6xl">
        <Link href="/" className="text-sm font-semibold text-[var(--color-brand)]">← Dashboard</Link>
        <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold sm:text-3xl">Content calendar</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--color-text-muted)]">Plan and review saved content, publishing history, and queued posts. Background dispatch supports Facebook Page text/link posts and TikTok video posts.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/content" className="rounded-xl bg-[var(--color-brand)] px-4 py-3 text-sm font-bold text-white">＋ Create content</Link>
            <Link href="/schedule-post" className="rounded-xl border border-[var(--color-border)] px-4 py-3 text-sm font-semibold">＋ Schedule post</Link>
          </div>
        </div>

        {error && <p role="alert" className="mt-5 rounded-xl border border-[var(--color-danger)] p-3 text-sm text-[var(--color-danger)]">{error}</p>}

        <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 shadow-[var(--shadow-card)] sm:p-5" aria-label="Content calendar">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => navigate(-1)} aria-label="Previous period" className="rounded-lg border border-[var(--color-border)] px-3 py-2 hover:bg-[var(--color-page)]">‹</button>
              <button type="button" onClick={() => setSelectedDate(startOfDay(new Date()))} className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-xs font-semibold hover:bg-[var(--color-page)]">Today</button>
              <button type="button" onClick={() => navigate(1)} aria-label="Next period" className="rounded-lg border border-[var(--color-border)] px-3 py-2 hover:bg-[var(--color-page)]">›</button>
              <h2 className="ml-1 text-base font-bold sm:ml-3 sm:text-lg">{heading}</h2>
            </div>
            <div className="flex rounded-xl bg-[var(--color-page)] p-1" role="group" aria-label="Calendar view">
              {(["month", "week", "agenda"] as CalendarView[]).map((option) => (
                <button key={option} type="button" onClick={() => setView(option)} aria-pressed={view === option} className={`rounded-lg px-3 py-2 text-xs font-semibold capitalize ${view === option ? "bg-[var(--color-brand)] text-white" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}>{option}</button>
              ))}
            </div>
          </div>

          {loading ? <p className="py-16 text-center text-sm text-[var(--color-text-muted)]">Loading calendar…</p> : view === "agenda" ? (
            <div className="mt-5 space-y-5">
              {visibleItems.length === 0 ? <p className="rounded-xl border border-dashed border-[var(--color-border)] p-10 text-center text-sm text-[var(--color-text-muted)]">No content in this 30-day period.</p> : visibleItems.map((item) => (
                <div key={`${item.kind}-${item.id}`} className="grid gap-2 sm:grid-cols-[130px_1fr]">
                  <div className="pt-2 text-sm font-semibold">{eventDate(item).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</div>
                  <EventCard item={item} />
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-5">
              <div className="grid grid-cols-7 border-b border-[var(--color-border)] pb-2 text-center text-[10px] font-bold uppercase tracking-wide text-[var(--color-text-muted)] sm:text-xs">
                {(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]).map((day) => <div key={day}>{day}</div>)}
              </div>
              <div className="grid grid-cols-7">
                {days.map((day) => {
                  const key = dateKey(day);
                  const dayItems = eventsByDay.get(key) || [];
                  const inMonth = day.getMonth() === selectedDate.getMonth();
                  const isToday = key === dateKey(new Date());
                  const isSelected = key === dateKey(selectedDate);
                  return (
                    <div key={key} className={`min-h-24 border-b border-r border-[var(--color-border)] p-1 sm:min-h-32 sm:p-2 ${!inMonth && view === "month" ? "bg-[var(--color-page)]/60" : ""}`}>
                      <button type="button" onClick={() => { setSelectedDate(day); setView("agenda"); }} aria-label={`Show events for ${day.toDateString()}`} className={`mb-1 flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${isToday ? "bg-[var(--color-brand)] text-white" : isSelected ? "bg-[var(--color-brand-soft)] text-[var(--color-brand)]" : ""} ${!inMonth && view === "month" ? "text-[var(--color-text-muted)] opacity-50" : ""}`}>{day.getDate()}</button>
                      <div className="space-y-1">
                        {dayItems.slice(0, 3).map((item) => <button key={`${item.kind}-${item.id}`} type="button" onClick={() => { setSelectedDate(day); setView("agenda"); }} className="block w-full rounded-md border-l-2 border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-1.5 py-1 text-left text-[9px] font-semibold leading-tight text-[var(--color-text)] sm:text-[10px]" title={`${item.title} · ${item.status}`}><span className="block truncate">{item.title}</span><span className="hidden font-normal opacity-75 sm:block">{item.platform} · {formatTime(eventDate(item))}</span></button>)}
                        {dayItems.length > 3 && <button type="button" onClick={() => { setSelectedDate(day); setView("agenda"); }} className="px-1 text-[9px] font-semibold text-[var(--color-brand)]">+{dayItems.length - 3} more</button>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>
        <p className="mt-4 text-xs text-[var(--color-text-muted)]">Calendar data includes saved drafts, Facebook Page posts, and TikTok/YouTube publishing jobs. TikTok video posts can now be scheduled for background publishing; provider-side cancellation and rescheduling remain limited to queued jobs.</p>
      </div>
    </main>
  );
}
