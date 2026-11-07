"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken } from "@/lib/auth";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

type Price = {
  id: string;
  plan_id: "standard" | "premium";
  currency: "NGN" | "USD";
  billing_interval: "monthly" | "annual";
  amount_minor: number;
  enabled: boolean;
  updated_at: string;
};

type Change = {
  id: string;
  plan_id: string;
  currency: string;
  billing_interval: string;
  previous_amount_minor: number | null;
  new_amount_minor: number;
  previous_enabled: boolean | null;
  new_enabled: boolean;
  actor_user_id: string | null;
  created_at: string;
};

type AdminPrices = { prices: Price[]; history: Change[] };

function money(amountMinor: number, currency: string) {
  return new Intl.NumberFormat(currency === "NGN" ? "en-NG" : "en-US", {
    style: "currency", currency, maximumFractionDigits: 2,
  }).format(amountMinor / 100);
}

function amountInput(price: Price) {
  return (price.amount_minor / 100).toFixed(price.currency === "USD" ? 2 : 0);
}

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init?.headers || {}) },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return payload as T;
}

export default function PlatformBillingPricesPage() {
  const router = useRouter();
  const [data, setData] = useState<AdminPrices | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async (token: string) => {
    const loaded = await api<AdminPrices>("/api/v1/billing/admin/prices", token);
    setData(loaded);
    setDrafts(Object.fromEntries(loaded.prices.map((price) => [price.id, amountInput(price)])));
    setEnabled(Object.fromEntries(loaded.prices.map((price) => [price.id, price.enabled])));
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { router.replace("/login"); return; }
    let cancelled = false;
    void refresh(token).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : "Price catalog could not be loaded.");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refresh, router]);

  async function save(price: Price) {
    const token = getAccessToken();
    if (!token) { router.replace("/login"); return; }
    const major = Number(drafts[price.id]);
    if (!Number.isFinite(major) || major <= 0) { setError("Enter a valid price greater than zero."); return; }
    setSaving(price.id); setError(""); setNotice("");
    try {
      await api<Price>("/api/v1/billing/admin/prices", token, {
        method: "PUT",
        body: JSON.stringify({
          plan_id: price.plan_id, currency: price.currency, billing_interval: price.billing_interval,
          amount_minor: Math.round(major * 100), enabled: enabled[price.id] ?? price.enabled,
        }),
      });
      await refresh(token);
      setNotice(`${price.plan_id} ${price.currency} ${price.billing_interval} price saved. Existing subscriptions are unchanged.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Price update failed.");
    } finally {
      setSaving("");
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl p-5 md:p-8">
      <div className="mb-7">
        <p className="mb-2 text-xs font-bold uppercase tracking-[.16em] text-[var(--color-brand)]">Platform administration</p>
        <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">Subscription pricing</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-muted)]">Manage the prices shown to new subscribers. Amounts are stored in NGN kobo or USD cents. A price change does not alter an existing customer's agreed subscription price.</p>
      </div>

      {error && <div role="alert" className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-700">{error}</div>}
      {notice && <div role="status" className="mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700">{notice}</div>}

      {loading ? <p className="text-sm text-[var(--text-muted)]">Loading price catalog…</p> : !data ? (
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-5">
          <h2 className="font-bold">Access unavailable</h2>
          <p className="mt-2 text-sm text-[var(--text-muted)]">This page is restricted to platform administrators. Confirm that your signed-in email is included in the backend PLATFORM_ADMIN_EMAILS setting.</p>
        </section>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-2">
            {data.prices.map((price) => (
              <article key={price.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-5 shadow-sm">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold capitalize">{price.plan_id}</h2>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">{price.currency} · {price.billing_interval}</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${enabled[price.id] ? "bg-emerald-500/10 text-emerald-700" : "bg-amber-500/10 text-amber-700"}`}>
                    {enabled[price.id] ? "Available" : "Disabled"}
                  </span>
                </div>
                <label className="mb-2 block text-xs font-semibold text-[var(--text-muted)]" htmlFor={`price-${price.id}`}>Price ({price.currency})</label>
                <div className="flex gap-2">
                  <input id={`price-${price.id}`} type="number" min="0.01" step={price.currency === "USD" ? "0.01" : "1"} value={drafts[price.id] ?? ""} onChange={(event) => setDrafts((current) => ({ ...current, [price.id]: event.target.value }))} className="min-w-0 flex-1 rounded-xl border border-[var(--color-border)] bg-[var(--page)] px-3 py-2.5 text-sm" />
                  <button type="button" disabled={saving === price.id} onClick={() => void save(price)} className="rounded-xl bg-[var(--color-brand)] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{saving === price.id ? "Saving…" : "Save"}</button>
                </div>
                <label className="mt-4 flex items-center gap-2 text-xs text-[var(--text-muted)]">
                  <input type="checkbox" checked={enabled[price.id] ?? price.enabled} onChange={(event) => setEnabled((current) => ({ ...current, [price.id]: event.target.checked }))} />
                  Allow new subscriptions at this price
                </label>
                <p className="mt-3 text-xs text-[var(--text-muted)]">Current stored amount: {money(price.amount_minor, price.currency)}</p>
              </article>
            ))}
          </section>

          <section className="mt-8 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-5">
            <h2 className="text-lg font-bold">Recent price changes</h2>
            <p className="mb-4 mt-1 text-xs text-[var(--text-muted)]">Audit history of the latest 100 updates.</p>
            {data.history.length === 0 ? <p className="text-sm text-[var(--text-muted)]">No price changes recorded yet.</p> : (
              <div className="space-y-3">
                {data.history.map((change) => (
                  <div key={change.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] pb-3 text-sm last:border-0">
                    <div><strong className="capitalize">{change.plan_id}</strong><span className="ml-2 text-xs text-[var(--text-muted)]">{change.currency} · {change.billing_interval}</span><p className="mt-1 text-xs text-[var(--text-muted)]">{change.previous_amount_minor === null ? "New price" : money(change.previous_amount_minor, change.currency)} → {money(change.new_amount_minor, change.currency)} · {change.new_enabled ? "Enabled" : "Disabled"}</p></div>
                    <time className="text-xs text-[var(--text-muted)]">{new Date(change.created_at).toLocaleString()}</time>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
