"use client";

import { Select } from "@/components/select";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, getStoredOrganization, type AuthOrganization } from "@/lib/auth";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
type Price = { id: string; plan_id: string; currency: "NGN" | "USD"; billing_interval: "monthly" | "annual"; amount_minor: number; enabled: boolean };
type Catalog = { prices_configured: boolean; checkout_enabled: boolean; plans: Array<{ id: string; name: string; prices: Price[] }> };
type Subscription = { plan_id: string; status: string; amount_minor: number | null; currency: string | null; billing_interval: string | null; current_period_end: string | null; cancel_at_period_end: boolean; grace_period_ends_at: string | null; provider: string; authorization_saved: boolean; authorization_card_last4: string | null; authorization_card_type: string | null; recurring_consent_recorded: boolean } | null;
type PaymentHistoryItem = { reference: string; provider: string; plan_id: string; billing_interval: string; amount_minor: number; currency: string; status: string; paid_at: string | null; created_at: string };
type RenewalAction = { reference: string; status: string; authorization_url: string | null; amount_minor: number; currency: string; plan_id: string; billing_interval: string; created_at: string };

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(init?.headers || {}) }, cache: "no-store" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status})`);
  return payload as T;
}
function formatMoney(amount: number, currency: string) {
  return new Intl.NumberFormat(currency === "NGN" ? "en-NG" : "en-US", { style: "currency", currency, maximumFractionDigits: 2 }).format(amount / 100);
}

export default function BillingPage() {
  const router = useRouter();
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [subscription, setSubscription] = useState<Subscription>(null);
  const [transactions, setTransactions] = useState<PaymentHistoryItem[]>([]);
  const [renewalActions, setRenewalActions] = useState<RenewalAction[]>([]);
  const [notice, setNotice] = useState("");
  const [currency, setCurrency] = useState<"NGN" | "USD">("NGN");
  const [interval, setInterval] = useState<"monthly" | "annual">("monthly");
  const [recurringConsent, setRecurringConsent] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const canManage = organization?.role === "owner" || organization?.role === "admin";

  const load = useCallback(async (token: string, org: AuthOrganization) => {
    const [prices, current, history, actions] = await Promise.all([
      api<Catalog>("/api/v1/billing/plans", token),
      api<{ subscription: Subscription }>(`/api/v1/billing/organizations/${org.id}/subscription`, token),
      api<{ transactions: PaymentHistoryItem[] }>(`/api/v1/billing/organizations/${org.id}/transactions`, token),
      api<{ actions: RenewalAction[] }>(`/api/v1/billing/organizations/${org.id}/renewal-actions`, token),
    ]);
    setCatalog(prices); setSubscription(current.subscription); setTransactions(history.transactions); setRenewalActions(actions.actions);
  }, []);

  useEffect(() => {
    const token = getAccessToken(); const active = getStoredOrganization();
    if (!token || !active) { router.replace("/login"); return; }
    setOrganization(active);
    void (async () => {
      try {
        await load(token, active);
        const returnedReference = new URLSearchParams(window.location.search).get("renewal_reference");
        if (returnedReference) {
          setBusy("renewal-verify");
          try {
            const result = await api<{ payment_status: string; message: string }>(`/api/v1/billing/organizations/${active.id}/renewal-actions/${encodeURIComponent(returnedReference)}/verify`, token, { method: "POST" });
            setNotice(result.message);
            await load(token, active);
          } catch (reason) { setError(reason instanceof Error ? reason.message : "The renewal could not be verified yet."); }
          finally { setBusy(""); window.history.replaceState({}, "", window.location.pathname); }
        }
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Billing information could not be loaded."); }
      finally { setLoading(false); }
    })();
  }, [load, router]);

  async function changeCancellation(action: "cancel" | "resume") {
    const token = getAccessToken(); if (!token || !organization) { router.replace("/login"); return; }
    setBusy(action); setError("");
    try {
      const result = await api<{ subscription: Subscription }>(`/api/v1/billing/organizations/${organization.id}/subscription/${action}`, token, { method: "POST" });
      setSubscription(result.subscription);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The subscription could not be updated."); }
    finally { setBusy(""); }
  }

  async function revokeAuthorization() {
    const token = getAccessToken(); if (!token || !organization) { router.replace("/login"); return; }
    if (!window.confirm("Deactivate the saved payment authorization? This prevents future automatic renewals from using this payment method. Your current paid access is not cancelled.")) return;
    setBusy("revoke-authorization"); setError("");
    try {
      const result = await api<{ subscription: Subscription }>(`/api/v1/billing/organizations/${organization.id}/subscription/authorization/revoke`, token, { method: "POST" });
      setSubscription(result.subscription);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The saved payment authorization could not be deactivated."); }
    finally { setBusy(""); }
  }


  async function verifyRenewal(reference: string) {
    const token = getAccessToken(); if (!token || !organization) { router.replace("/login"); return; }
    setBusy(`verify-${reference}`); setError(""); setNotice("");
    try {
      const result = await api<{ message: string }>(`/api/v1/billing/organizations/${organization.id}/renewal-actions/${encodeURIComponent(reference)}/verify`, token, { method: "POST" });
      setNotice(result.message); await load(token, organization);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The renewal could not be verified yet."); }
    finally { setBusy(""); }
  }

  async function checkout(planId: string) {
    const token = getAccessToken(); if (!token || !organization) { router.replace("/login"); return; }
    setBusy(planId); setError("");
    try {
      const result = await api<{ authorization_url: string }>(`/api/v1/billing/organizations/${organization.id}/checkout`, token, {
        method: "POST", body: JSON.stringify({ plan_id: planId, currency, billing_interval: interval, provider: "paystack", recurring_consent: recurringConsent }),
      });
      window.location.assign(result.authorization_url);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Checkout could not be started."); setBusy(""); }
  }

  const available = catalog?.plans.flatMap((plan) => plan.prices).filter((price) => price.currency === currency && price.billing_interval === interval && price.enabled) ?? [];
  return <main className="mx-auto w-full max-w-6xl p-5 pb-24 md:p-8">
    <header className="mb-7"><p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--color-brand)]">Workspace billing</p><h1 className="mt-2 text-3xl font-extrabold">Plans & subscription</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-muted)]">Manage the plan for {organization?.name ?? "your workspace"}. Payments are securely processed through Paystack Checkout.</p></header>
    {notice && <p role="status" className="mb-5 rounded-xl border border-[var(--color-brand)]/30 bg-[var(--color-brand-soft)] p-3 text-sm">{notice}</p>}
    {error && <p role="alert" className="mb-5 rounded-xl border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 p-3 text-sm text-[var(--color-danger)]">{error}</p>}
    {loading ? <p className="text-sm text-[var(--color-text-muted)]">Loading billing…</p> : <>
      <section className="mb-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">Current subscription</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Your workspace's active plan and billing period.</p></div><span className="rounded-full bg-[var(--color-brand-soft)] px-3 py-1 text-xs font-bold capitalize text-[var(--color-brand)]">{subscription?.status ?? "Free plan"}</span></div>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-3"><div><p className="text-2xl font-extrabold capitalize">{subscription?.plan_id ?? "Free"}</p>{subscription?.amount_minor && subscription.currency ? <p className="mt-1 text-sm text-[var(--color-text-muted)]">{formatMoney(subscription.amount_minor, subscription.currency)} / {subscription.billing_interval}</p> : <p className="mt-1 text-sm text-[var(--color-text-muted)]">No paid subscription is active.</p>}</div>{subscription?.current_period_end && <p className="text-xs text-[var(--color-text-muted)]">Current period ends {new Date(subscription.current_period_end).toLocaleDateString()}</p>}</div>
        {subscription?.grace_period_ends_at && <p className="mt-3 rounded-lg border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 p-3 text-sm">Payment is overdue. Your current plan remains available during the renewal grace period until {new Date(subscription.grace_period_ends_at).toLocaleDateString()}.</p>}
        {subscription?.cancel_at_period_end && <p className="mt-3 rounded-lg border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 p-3 text-sm">Cancellation is scheduled. Your paid access remains active until the end of this billing period.</p>}
        {canManage && subscription?.status === "active" && !subscription.cancel_at_period_end && <button type="button" disabled={!!busy} onClick={() => void changeCancellation("cancel")} className="mt-4 rounded-lg border border-[var(--color-danger)]/40 px-4 py-2 text-sm font-semibold text-[var(--color-danger)] disabled:opacity-50">{busy === "cancel" ? "Updating…" : "Cancel subscription at period end"}</button>}
        {canManage && subscription?.cancel_at_period_end && <button type="button" disabled={!!busy} onClick={() => void changeCancellation("resume")} className="mt-4 rounded-lg border border-[var(--color-brand)]/40 px-4 py-2 text-sm font-semibold text-[var(--color-brand)] disabled:opacity-50">{busy === "resume" ? "Updating…" : "Keep my subscription"}</button>}
        {subscription?.authorization_saved && <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-bold">Saved payment authorization</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{subscription.authorization_card_type ? `${subscription.authorization_card_type} card` : "Paystack payment method"}{subscription.authorization_card_last4 ? ` ending in ${subscription.authorization_card_last4}` : ""}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">This authorization is securely stored for possible future renewals. Automatic renewals are not currently enabled.</p></div>
          {organization?.role === "owner" && <button type="button" disabled={!!busy} onClick={() => void revokeAuthorization()} className="rounded-lg border border-[var(--color-danger)]/40 px-3 py-2 text-xs font-semibold text-[var(--color-danger)] disabled:opacity-50">{busy === "revoke-authorization" ? "Deactivating…" : "Deactivate saved method"}</button>}</div>
        </div>}
        {subscription?.recurring_consent_recorded && !subscription.authorization_saved && <p className="mt-3 rounded-lg border border-[var(--color-border)] p-3 text-xs text-[var(--color-text-muted)]">You previously provided recurring-payment consent, but there is no reusable payment authorization currently stored.</p>}
      </section>
      {renewalActions.length > 0 && <section className="mb-7 rounded-2xl border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/5 p-5"><h2 className="font-bold">Payment authentication required</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Your bank or card provider requires an additional security step for this renewal. Complete it securely with Paystack, then return here to verify the payment. If you are a workspace member, ask an owner or admin to complete this step.</p><div className="mt-4 space-y-3">{renewalActions.map((action) => <div key={action.reference} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"><div><p className="text-sm font-semibold capitalize">{action.plan_id} · {action.billing_interval}</p><p className="text-xs text-[var(--color-text-muted)]">{formatMoney(action.amount_minor, action.currency)} · {new Date(action.created_at).toLocaleString()}</p></div><div className="flex flex-wrap gap-2">{action.authorization_url && <a href={action.authorization_url} target="_blank" rel="noopener noreferrer" className="rounded-lg bg-[var(--color-brand)] px-3 py-2 text-xs font-bold text-white">Complete authentication</a>}{canManage && <button type="button" disabled={!!busy} onClick={() => void verifyRenewal(action.reference)} className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-xs font-semibold disabled:opacity-50">{busy === `verify-${action.reference}` ? "Checking…" : "Verify payment"}</button>}</div></div>)}</div></section>}
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5"><div className="mb-4"><h2 className="font-bold">Payment history</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Recent subscription payment attempts and their status.</p></div>{transactions.length === 0 ? <p className="text-sm text-[var(--color-text-muted)]">No payment transactions yet.</p> : <div className="space-y-3">{transactions.map((item) => <div key={item.reference} className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] pb-3 last:border-0"><div><p className="text-sm font-semibold capitalize">{item.plan_id} · {item.billing_interval}</p><p className="text-xs text-[var(--color-text-muted)]">{new Date(item.created_at).toLocaleString()} · {item.provider}</p><p className="text-xs text-[var(--color-text-muted)]">Ref: {item.reference}</p></div><div className="text-right"><p className="text-sm font-bold">{formatMoney(item.amount_minor, item.currency)}</p><span className="text-xs font-semibold capitalize text-[var(--color-text-muted)]">{item.status}</span></div></div>)}</div>}</section>
      <section className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><h2 className="text-xl font-bold">Choose a plan</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Annual billing is priced at ten monthly payments.</p></div><div className="flex flex-wrap gap-2"><label className="text-xs font-semibold text-[var(--color-text-muted)]">Currency<Select value={currency} onChange={(event) => setCurrency(event.target.value as "NGN" | "USD")} className="mt-1 block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)]"><option value="NGN">NGN — Naira</option><option value="USD">USD — US Dollar</option></Select></label><label className="text-xs font-semibold text-[var(--color-text-muted)]">Billing interval<Select value={interval} onChange={(event) => setInterval(event.target.value as "monthly" | "annual")} className="mt-1 block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)]"><option value="monthly">Monthly</option><option value="annual">Annual</option></Select></label></div></section>
      {!catalog?.checkout_enabled && <p className="mb-5 rounded-xl border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 p-3 text-sm">Online checkout is not yet enabled. The administrator must configure Paystack credentials and webhook verification.</p>}
      <p className="mb-3 rounded-lg border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 p-3 text-sm">Automatic recurring charges are not active yet. This optional consent only allows a reusable authorization to be securely prepared for possible future renewals; you will be notified before automatic billing is activated.</p>
      <section className="mb-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <label className="flex items-start gap-3 text-sm leading-6"><input type="checkbox" checked={recurringConsent} onChange={(event) => setRecurringConsent(event.target.checked)} className="mt-1 h-4 w-4 accent-[var(--color-brand)]" /><span><strong>Prepare future automatic renewal (optional).</strong> I consent to BizPilotPro securely retaining a reusable payment authorization for future renewals. Automatic renewal is not active yet; no future automatic charge will be made until the feature is activated and I am notified. If activated, the selected plan price will be charged monthly or annually as selected until I cancel before a renewal. The first payment is charged now. If I leave this unchecked, this purchase is a one-time payment and no reusable authorization will be retained.</span></label>
      </section>
      <section className="grid gap-4 md:grid-cols-2">{["standard", "premium"].map((planId) => { const price = available.find((item) => item.plan_id === planId); return <article key={planId} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6"><p className="text-xs font-bold uppercase tracking-widest text-[var(--color-brand)]">{planId === "premium" ? "For growing teams" : "For getting started"}</p><h3 className="mt-2 text-2xl font-extrabold capitalize">{planId}</h3><p className="mt-3 text-3xl font-extrabold">{price ? formatMoney(price.amount_minor, currency) : "Unavailable"}<span className="ml-1 text-xs font-medium text-[var(--color-text-muted)]">/{interval === "annual" ? "year" : "month"}</span></p><p className="mt-3 min-h-10 text-sm text-[var(--color-text-muted)]">{planId === "standard" ? "More room for consistent social content and scheduling." : "Higher monthly limits for businesses with a heavier content workflow."}</p><button type="button" disabled={!canManage || !price || !catalog?.checkout_enabled || !!busy} onClick={() => void checkout(planId)} className="mt-5 w-full rounded-xl bg-[var(--color-brand)] px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy === planId ? "Connecting to Paystack…" : `Subscribe to ${planId}`}</button>{!canManage && <p className="mt-2 text-xs text-[var(--color-text-muted)]">Only workspace owners and admins can change the subscription.</p>}</article>; })}</section>
      {!catalog?.prices_configured && <p className="mt-5 text-xs text-[var(--color-text-muted)]">The pricing catalog has not been seeded in this database yet. Apply the latest Alembic migrations.</p>}
      <p className="mt-6 text-xs leading-5 text-[var(--color-text-muted)]">Paystack Checkout may offer Google Pay when enabled for the merchant account and supported by the customer's device and payment card. PayPal and Flutterwave are future integrations, not currently available payment options.</p>
      <p className="mt-4 text-xs text-[var(--color-text-muted)]">Need to update your account details? Visit <Link className="font-semibold text-[var(--color-brand)] underline" href="/security">Account security</Link> or <Link className="font-semibold text-[var(--color-brand)] underline" href="/workspace">Workspace settings</Link>.</p>
    </>}
  </main>;
}
