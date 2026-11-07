"use client";

import { Select } from "@/components/select";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getAccessToken, getStoredOrganization, type AuthOrganization } from "@/lib/auth";
import { inputClass } from "@/components/auth-shell";
import { ACTIVITY_CATEGORIES, fetchActivity, type ActivityEntry } from "@/lib/activity";

const PAGE_SIZE = 50;

export default function ActivityPage() {
  const router = useRouter();
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("");

  const canView = organization?.role === "owner" || organization?.role === "admin";

  useEffect(() => {
    const token = getAccessToken();
    const active = getStoredOrganization();
    if (!token || !active) {
      router.replace("/login");
      return;
    }
    setOrganization(active);
    if (active.role !== "owner" && active.role !== "admin") {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchActivity(token, active.id, PAGE_SIZE, 0, category)
      .then((loaded) => {
        if (cancelled) return;
        setEntries(loaded);
        setHasMore(loaded.length === PAGE_SIZE);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Something went wrong. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [router, category]);

  async function loadMore() {
    const token = getAccessToken();
    if (!token || !organization) return;
    setLoadingMore(true);
    setError("");
    try {
      const next = await fetchActivity(token, organization.id, PAGE_SIZE, entries.length, category);
      setEntries((current) => [...current, ...next]);
      setHasMore(next.length === PAGE_SIZE);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Something went wrong. Please try again.");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <main className="min-h-screen bg-[var(--color-page)] px-4 py-8 text-[var(--color-text)] sm:px-6">
      <div className="mx-auto w-full max-w-3xl">
        <Link href="/" className="text-sm font-bold text-[var(--color-brand)] hover:underline">← Back to dashboard</Link>
        <section className="mt-4 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl sm:p-8">
          <p className="text-sm font-bold text-[var(--color-brand)]">ACTIVITY LOG</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight">What your team did</h1>
          <p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">Who signed in, created, edited, approved, generated, or deleted things in {organization?.name || "this workspace"}. Entries cannot be changed or removed.</p>

          {canView ? (
            <div className="mt-5">
              <label htmlFor="activity-category" className="mb-2 block text-sm font-semibold">Show</label>
              <Select id="activity-category" value={category} onChange={(event) => { setEntries([]); setHasMore(false); setCategory(event.target.value); }} className={inputClass}>
                {ACTIVITY_CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </Select>
            </div>
          ) : null}

          {error ? <div role="alert" className="mt-4 rounded-xl border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 px-4 py-3 text-sm leading-5 text-[var(--color-danger)]">{error}</div> : null}

          {loading ? (
            <p className="mt-6 text-sm text-[var(--color-text-muted)]">Loading…</p>
          ) : !canView ? (
            <p role="status" className="mt-6 text-sm">Only workspace owners and admins can view the activity log.</p>
          ) : entries.length === 0 && !error ? (
            <p className="mt-6 text-sm text-[var(--color-text-muted)]">{category ? "No matching activity yet." : "No activity yet."}</p>
          ) : (
            <>
              <ul className="mt-6 divide-y divide-[var(--color-border)]">
                {entries.map((entry) => (
                  <li key={entry.id} className="py-4">
                    <p className="text-sm leading-6"><span className="font-bold">{entry.actor_name}</span> · {entry.summary}</p>
                    <p className="mt-1 text-xs text-[var(--color-text-muted)]">{new Date(entry.created_at).toLocaleString()}</p>
                  </li>
                ))}
              </ul>
              {hasMore ? <button type="button" onClick={loadMore} disabled={loadingMore} className="mt-4 w-full rounded-xl border border-[var(--color-border)] px-4 py-3 text-sm font-semibold hover:bg-[var(--color-surface-raised)] disabled:opacity-60">{loadingMore ? "Loading…" : "Load more"}</button> : null}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
