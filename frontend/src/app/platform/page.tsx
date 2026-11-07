"use client";

import { Select } from "@/components/select";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getAccessToken } from "@/lib/auth";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
type Org = { id: string; name: string; slug: string; role: string; plan: string; subscription: null | { status: string; plan_id: string; provider: string; currency: string | null; amount_minor: number | null; billing_interval: string | null; current_period_end: string | null } };
type Customer = { id: string; email: string | null; full_name: string; is_active: boolean; email_verified: boolean; created_at: string; organizations: Org[] };
type PageData = { items: Customer[]; total: number; limit: number; offset: number };
type Overview = { customers: number; active_customers: number; organizations: number; active_subscriptions: number; pending_payments: number; failed_webhooks: number };
type Transaction = { reference: string; provider: string; status: string; amount_minor: number; currency: string; plan_id: string; billing_interval: string; created_at: string; paid_at: string | null };
type CustomerDetail = Customer & { payment_transactions: Transaction[] };
type TopCustomer = { rank: number; user_id: string; full_name: string; email: string | null; is_active: boolean; total_spend_minor: number; currency: string; successful_payment_count: number; last_payment_at: string | null };
type AdminAudit = { id: string; actor_user_id: string; target_user_id: string | null; action: string; summary: string; created_at: string };
type CostEntry = {id:string;category:string;provider:string;description:string;amount_minor:number;currency:string;period_start:string;period_end:string;created_at:string};
type Financials = { payment_adjustments?:{type:string;status:string;currency:string;amount_minor:number;events:number}[]; refund_chargeback_note?:string; ai_usage_by_model?:{provider:string;model:string;feature:string;prompt_tokens:number;completion_tokens:number;total_tokens:number;estimated_cost_usd_micros:number|null;events:number}[]; ai_cost_estimation?:{configured:boolean;note:string}; recorded_costs_by_currency:{currency:string;recorded_cost_minor:number;entries:number}[]; period_days: number; revenue_by_currency: {currency:string;paid_amount_minor:number;paid_transactions:number}[]; pending_by_currency:{currency:string;pending_amount_minor:number;pending_transactions:number}[]; usage_by_metric:{metric:string;quantity:number;events:number}[]; cost_tracking:{available:boolean;reason:string}; profitability:{available:boolean;reason:string}; currency_note:string };
type PlatformEvent = {id:string; created_at:string; action?:string; summary?:string; actor_name?:string; actor_email?:string; organization?:string; email?:string; full_name?:string; method?:string};
type DelegatedAdmin = {id:string;user_id:string;email:string;full_name:string;role:string;created_at:string};
type SecuritySession = {event_id:string;user_id:string;email:string;full_name:string;method:string;ip_address:string|null;user_agent:string|null;success:boolean;created_at:string;session_status:string};
type FailedLogin = {id:string;email:string;ip_address:string|null;method:string;created_at:string};
type EmailCampaign = {id:string;subject:string;status:string;recipient_count:number;sent_count:number;failed_count:number;created_at:string;completed_at:string|null};
type EmailCampaignAnalytics = {campaign_id:string;status:string;recipient_count:number;sent_count:number;delivered_count:number;pending_count:number;retry_count:number;failed_count:number;bounced_count:number;complained_count:number;unsubscribed_count:number};
type BillingOps = { paystack: { credentials_configured: boolean; webhook_secret_configured: boolean; mode: string; google_pay: string }; transactions: { reference: string; provider: string; status: string; amount_minor: number; currency: string; plan_id: string; created_at: string }[]; webhooks: { id: string; event_type: string; reference: string | null; status: string; received_at: string; processed_at: string | null; failure_message: string | null }[]; live_verification: string };

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}/api/v1${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(init?.headers || {}) }, cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`);
  return body as T;
}
function money(minor: number | null, currency: string | null) { return minor === null || !currency ? "—" : new Intl.NumberFormat(currency === "NGN" ? "en-NG" : "en-US", { style: "currency", currency }).format(minor / 100); }

export default function PlatformAdminPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [billingOps, setBillingOps] = useState<BillingOps | null>(null);
  const [financials, setFinancials] = useState<Financials | null>(null);
  const [platformActivity, setPlatformActivity] = useState<PlatformEvent[]>([]);
  const [loginEvents, setLoginEvents] = useState<PlatformEvent[]>([]);
  const [costEntries, setCostEntries] = useState<CostEntry[]>([]);
  const [costForm, setCostForm] = useState({category:"hosting",provider:"",description:"",amount:"",currency:"NGN",period_start:new Date().toISOString().slice(0,10),period_end:new Date().toISOString().slice(0,10)});
  const [audits, setAudits] = useState<AdminAudit[]>([]);
  const [topCustomers, setTopCustomers] = useState<TopCustomer[]>([]);
  const [topCurrency, setTopCurrency] = useState("NGN");
  const [topSort, setTopSort] = useState("desc");
  const [data, setData] = useState<PageData | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [recoveryReason, setRecoveryReason] = useState("");
  const [delegatedAdmins, setDelegatedAdmins] = useState<DelegatedAdmin[]>([]);
  const [canManageAdmins, setCanManageAdmins] = useState(false);
  const [adminEmail, setAdminEmail] = useState("");
  const [adminRole, setAdminRole] = useState("support");
  const [campaignSubject, setCampaignSubject] = useState("");
  const [campaignBody, setCampaignBody] = useState("");
  const [recipientCount, setRecipientCount] = useState(0);
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [campaignAnalytics, setCampaignAnalytics] = useState<Record<string, EmailCampaignAnalytics>>({});
  const [securitySessions, setSecuritySessions] = useState<SecuritySession[]>([]);
  const [failedAdminLogins, setFailedAdminLogins] = useState<FailedLogin[]>([]);

  const refresh = useCallback(async (auth: string, nextOffset = offset) => {
    const params = new URLSearchParams({ limit: "25", offset: String(nextOffset), status });
    const topParams = new URLSearchParams({ limit: "10", currency: topCurrency, sort: topSort });
    if (query.trim()) params.set("q", query.trim());
    const [summary, customers, operations, auditData, topData, financialData, activityData, loginData, costData] = await Promise.all([
      api<Overview>("/platform-admin/overview", auth),
      api<PageData>(`/platform-admin/customers?${params}`, auth),
      api<BillingOps>("/platform-admin/billing-operations", auth),
      api<{ items: AdminAudit[] }>("/platform-admin/audit?limit=20", auth),
      api<{ items: TopCustomer[] }>(`/platform-admin/top-customers?${topParams}`, auth),
      api<Financials>("/platform-admin/financials?days=90", auth),
      api<{items:PlatformEvent[]}>("/platform-admin/activity?limit=30", auth),
      api<{items:PlatformEvent[]}>("/platform-admin/login-events?limit=30", auth),
      api<{items:CostEntry[]}>("/platform-admin/cost-entries?limit=100", auth),
    ]);
    setOverview(summary); setData(customers); setBillingOps(operations); setAudits(auditData.items); setTopCustomers(topData.items); setFinancials(financialData); setPlatformActivity(activityData.items); setLoginEvents(loginData.items); setCostEntries(costData.items); setOffset(nextOffset);
  }, [offset, query, status, topCurrency, topSort]);

  const refreshRef = useRef(refresh);
  useEffect(() => { refreshRef.current = refresh; }, [refresh]);
  useEffect(() => {
    const auth = getAccessToken();
    if (!auth) { router.replace("/admin/login"); return; }
    setToken(auth);
    void api<{items:DelegatedAdmin[]}>('/platform-admin/admins', auth).then((result) => {
      setDelegatedAdmins(result.items); setCanManageAdmins(true);
      void Promise.all([
        api<{recipient_count:number}>('/platform-admin/email-campaigns/recipient-count', auth),
        api<{items:EmailCampaign[]}>('/platform-admin/email-campaigns', auth),
        api<{items:SecuritySession[]}>('/platform-admin/security/sessions', auth),
        api<{items:FailedLogin[]}>('/platform-admin/security/failed-logins', auth),
      ]).then(([count, history, sessions, failures]) => { setRecipientCount(count.recipient_count); setCampaigns(history.items); setSecuritySessions(sessions.items); setFailedAdminLogins(failures.items); }).catch((reason:unknown)=>setError(reason instanceof Error ? reason.message : 'Owner security tools could not be loaded.'));
    }).catch(() => { setCanManageAdmins(false); });
    let alive = true;
    void refreshRef.current(auth, 0).catch((reason: unknown) => { if (alive) setError(reason instanceof Error ? reason.message : "Platform data could not be loaded."); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [router]);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    const params = new URLSearchParams({ limit: "10", currency: topCurrency, sort: topSort });
    api<{ items: TopCustomer[] }>(`/platform-admin/top-customers?${params}`, token)
      .then((result) => { if (alive) setTopCustomers(result.items); })
      .catch((reason: unknown) => { if (alive) setError(reason instanceof Error ? reason.message : "Customer leaderboard could not be loaded."); });
    return () => { alive = false; };
  }, [token, topCurrency, topSort]);

  async function openCustomer(customer: Customer) {
    setError("");
    try { setSelected(await api<CustomerDetail>(`/platform-admin/customers/${customer.id}`, token)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Customer details could not be loaded."); }
  }
  async function retryWebhook(eventId: string) {
    if (!window.confirm("Retry this failed webhook? The server will verify the payment directly with Paystack before changing any subscription.")) return;
    setBusy(eventId); setError(""); setNotice("");
    try {
      const result = await api<{ status: string; message: string }>(`/platform-admin/webhooks/${eventId}/retry`, token, { method: "POST" });
      setNotice(result.message); await refresh(token, offset);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Webhook retry failed."); }
    finally { setBusy(""); }
  }

  async function addCostEntry() {
    const amount = Number(costForm.amount);
    if (!costForm.provider.trim() || !costForm.description.trim() || !Number.isFinite(amount) || amount <= 0) {
      setError("Enter a provider, description and a valid positive cost amount."); return;
    }
    setBusy("cost-entry"); setError(""); setNotice("");
    try {
      await api("/platform-admin/cost-entries", token, {method:"POST", body:JSON.stringify({
        category:costForm.category, provider:costForm.provider.trim(), description:costForm.description.trim(),
        amount_minor:Math.round(amount*100), currency:costForm.currency,
        period_start:costForm.period_start, period_end:costForm.period_end,
      })});
      setNotice("Verified operating cost recorded."); setCostForm({...costForm,provider:"",description:"",amount:""});
      await refresh(token, offset);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not record operating cost."); }
    finally { setBusy(""); }
  }

  async function runReconciliation() {
    if (!window.confirm("Check pending Paystack payments older than 10 minutes? Successful payments will only activate after fresh server-side verification.")) return;
    setBusy("reconciliation"); setError(""); setNotice("");
    try {
      const result = await api<{ examined: number; activated: number; failed: number; needs_attention: number; provider_unavailable: number }>(
        "/platform-admin/billing/reconciliation/run", token,
        { method: "POST", body: JSON.stringify({ limit: 50, older_than_minutes: 10 }) },
      );
      setNotice(`Reconciliation checked ${result.examined} payment(s): ${result.activated} activated, ${result.failed} failed, ${result.needs_attention} need attention, ${result.provider_unavailable} provider errors.`);
      await refresh(token, offset);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Payment reconciliation failed."); }
    finally { setBusy(""); }
  }

  async function initiatePasswordRecovery(customer: CustomerDetail) {
    if (recoveryReason.trim().length < 20) {
      setError("Enter a support reason of at least 20 characters before sending a recovery link.");
      return;
    }
    if (!customer.email_verified) {
      setError("This customer does not have a verified email address. Use the manual identity-verification support process.");
      return;
    }
    if (!window.confirm(`Send a one-time password reset link to ${customer.email}? The customer will choose their own new password.`)) return;
    setBusy(`recovery-${customer.id}`); setError(""); setNotice("");
    try {
      const result = await api<{ message: string }>(`/platform-admin/customers/${customer.id}/password-recovery`, token, {
        method: "POST", body: JSON.stringify({ reason: recoveryReason.trim() }),
      });
      setNotice(result.message); setRecoveryReason("");
      await refresh(token, offset);
      await openCustomer(customer);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Password recovery could not be initiated."); }
    finally { setBusy(""); }
  }

  async function changeStatus(customer: CustomerDetail) {
    const action = customer.is_active ? "suspend" : "reactivate";
    if (!window.confirm(`Are you sure you want to ${action} ${customer.email || customer.full_name}?${customer.is_active ? " Their current sessions will be invalidated." : ""}`)) return;
    setBusy(customer.id); setError(""); setNotice("");
    try {
      await api(`/platform-admin/customers/${customer.id}/status`, token, { method: "PATCH", body: JSON.stringify({ is_active: !customer.is_active }) });
      setNotice(`Customer ${action}d successfully.`); setSelected(null); await refresh(token, offset);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Account status could not be changed."); }
    finally { setBusy(""); }
  }

  async function grantAdminRole() {
    if (!adminEmail.trim()) { setError("Enter the registered email address of the administrator."); return; }
    setBusy("admin-role"); setError(""); setNotice("");
    try {
      await api('/platform-admin/admins', token, {method:'POST', body:JSON.stringify({email:adminEmail.trim(),role:adminRole})});
      const result = await api<{items:DelegatedAdmin[]}>('/platform-admin/admins', token);
      setDelegatedAdmins(result.items); setAdminEmail(""); setNotice("Administrator role saved. The user must enable authenticator MFA before accessing the admin platform.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Administrator role could not be saved."); }
    finally { setBusy(""); }
  }
  async function revokeAdminRole(userId:string) {
    if (!window.confirm("Revoke this user's delegated platform administrator access?")) return;
    setBusy(userId); setError(""); setNotice("");
    try {
      await api(`/platform-admin/admins/${userId}`, token, {method:'DELETE'});
      setDelegatedAdmins((items)=>items.filter((item)=>item.user_id!==userId)); setNotice("Delegated administrator access revoked.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Administrator access could not be revoked."); }
    finally { setBusy(""); }
  }

  async function sendPlatformAnnouncement() {
    if (campaignSubject.trim().length < 3 || campaignBody.trim().length < 10) { setError("Enter a subject and a message of at least 10 characters."); return; }
    if (!window.confirm(`Send this announcement to all ${recipientCount} registered users with verified email addresses? This cannot be recalled.`)) return;
    setBusy("email-campaign"); setError(""); setNotice("");
    try {
      const result = await api<{id:string;recipient_count:number;message:string}>("/platform-admin/email-campaigns", token, {method:"POST", body:JSON.stringify({subject:campaignSubject.trim(),body:campaignBody.trim(),confirm_all_recipients:true})});
      setNotice(`${result.message} ${result.recipient_count} recipients queued.`); setCampaignSubject(""); setCampaignBody("");
      const history = await api<{items:EmailCampaign[]}>("/platform-admin/email-campaigns", token); setCampaigns(history.items);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Email campaign could not be queued."); }
    finally { setBusy(""); }
  }
  async function loadCampaignAnalytics(campaignId:string) {
    if (!token) return;
    setBusy(`analytics-${campaignId}`);
    try {
      const result = await api<EmailCampaignAnalytics>(`/platform-admin/email-campaigns/${campaignId}/analytics`, token);
      setCampaignAnalytics(current => ({...current, [campaignId]: result}));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Campaign analytics could not be loaded."); }
    finally { setBusy(""); }
  }

  async function retryEmailCampaign(campaignId:string) {
    if (!window.confirm("Re-queue failed recipients for another delivery attempt?")) return;
    setBusy(`campaign-${campaignId}`); setError(""); setNotice("");
    try { const result=await api<{requeued:number;message:string}>(`/platform-admin/email-campaigns/${campaignId}/retry-failed`,token,{method:"POST"}); setNotice(result.message); const history=await api<{items:EmailCampaign[]}>("/platform-admin/email-campaigns",token); setCampaigns(history.items); }
    catch(reason) { setError(reason instanceof Error ? reason.message : "Failed recipients could not be re-queued."); }
    finally { setBusy(""); }
  }
  async function revokeAdminUserSessions(userId:string, email:string) {
    if (!window.confirm(`Revoke every active login session for ${email}? They will need to sign in again.`)) return;
    setBusy(`session-${userId}`); setError(""); setNotice("");
    try { const result=await api<{message:string}>(`/platform-admin/security/users/${userId}/revoke-sessions`,token,{method:"POST"}); setNotice(result.message); }
    catch(reason) { setError(reason instanceof Error ? reason.message : "Sessions could not be revoked."); }
    finally { setBusy(""); }
  }

  return <main className="mx-auto w-full max-w-7xl p-5 md:p-8">
    <div className="mb-7 flex flex-wrap items-start justify-between gap-4"><div><p className="mb-2 text-xs font-bold uppercase tracking-[.16em] text-[var(--color-brand)]">Restricted · platform owner</p><h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">Platform administration</h1><p className="mt-2 max-w-3xl text-sm text-[var(--text-muted)]">Manage customer access, inspect organisations and review subscription and payment status.</p></div><div className="flex gap-2"><Link className="rounded-xl border border-[var(--color-border)] px-3 py-2 text-sm font-semibold" href="/platform/billing-prices">Manage prices</Link><Link className="rounded-xl border border-[var(--color-border)] px-3 py-2 text-sm font-semibold" href="/billing">Customer billing</Link></div></div>
    {canManageAdmins && <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">Administrator access</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Only the configured platform owner can grant or revoke delegated roles. Every delegated administrator must enable MFA.</p></div><span className="text-xs text-[var(--text-muted)]">Owner-only controls</span></div><div className="mt-4 grid gap-3 md:grid-cols-[1fr_180px_auto]"><label className="text-xs font-semibold">Registered user email<input value={adminEmail} onChange={e=>setAdminEmail(e.target.value)} placeholder="admin@example.com" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"/></label><label className="text-xs font-semibold">Role<select value={adminRole} onChange={e=>setAdminRole(e.target.value)} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"><option value="support">Support</option><option value="finance">Finance</option><option value="operations">Operations</option><option value="viewer">Read-only</option></select></label><button type="button" disabled={busy==="admin-role" || !adminEmail.trim()} onClick={()=>void grantAdminRole()} className="self-end rounded-lg bg-[var(--color-brand)] px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{busy==="admin-role"?"Saving…":"Grant / update role"}</button></div><div className="mt-4 divide-y divide-[var(--color-border)]">{delegatedAdmins.map((admin)=><div key={admin.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><div><strong>{admin.full_name || admin.email}</strong><p className="text-xs text-[var(--text-muted)]">{admin.email} · <span className="capitalize">{admin.role.replace('_',' ')}</span></p></div><button type="button" disabled={busy===admin.user_id} onClick={()=>void revokeAdminRole(admin.user_id)} className="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs font-semibold text-red-700 disabled:opacity-50">Revoke access</button></div>)}{!delegatedAdmins.length && <p className="py-3 text-xs text-[var(--text-muted)]">No delegated administrators have been assigned. If you are not the configured owner, this section is not available to manage.</p>}</div></section>}
    {canManageAdmins && <>
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-bold">Email registered users</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Send a platform announcement to all registered accounts with verified email addresses.</p></div><strong className="text-sm tabular-nums">{recipientCount.toLocaleString()} recipients</strong></div>
        <label className="mt-4 block text-xs font-semibold">Email subject<input maxLength={180} value={campaignSubject} onChange={e=>setCampaignSubject(e.target.value)} placeholder="Important AutoBizPro update" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-3 text-sm"/></label>
        <label className="mt-3 block text-xs font-semibold">Message<textarea rows={7} maxLength={12000} value={campaignBody} onChange={e=>setCampaignBody(e.target.value)} placeholder="Write your update here…" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-3 text-sm"/></label>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><p className="max-w-2xl text-xs text-[var(--text-muted)]">Campaigns are stored durably and processed by the scheduled backend worker. Configure SMTP or the Resend campaign provider; Resend webhooks update delivered, bounced and complaint states. Recipients can unsubscribe from future announcements. Use this for platform and account updates, not unsolicited marketing.</p><button type="button" disabled={busy==="email-campaign" || !campaignSubject.trim() || campaignBody.trim().length<10 || recipientCount===0} onClick={()=>void sendPlatformAnnouncement()} className="rounded-lg bg-[var(--color-brand)] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{busy==="email-campaign"?"Queueing…":"Send to all users"}</button></div>
        <h3 className="mt-6 text-sm font-bold">Campaign history</h3><div className="mt-2 divide-y divide-[var(--color-border)]">{campaigns.map(c=><div key={c.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><div><strong>{c.subject}</strong><p className="text-xs text-[var(--text-muted)]">{new Date(c.created_at).toLocaleString()} · {c.recipient_count} recipients · {c.sent_count} sent · {c.failed_count} failed</p></div><div className="flex items-center gap-2"><span className="text-xs font-semibold capitalize">{c.status.replaceAll("_"," ")}</span><button type="button" disabled={busy===`analytics-${c.id}`} onClick={()=>void loadCampaignAnalytics(c.id)} className="rounded-lg border border-[var(--color-border)] px-2 py-1 text-xs font-semibold disabled:opacity-50">Analytics</button>{c.failed_count>0&&<button type="button" disabled={busy===`campaign-${c.id}`} onClick={()=>void retryEmailCampaign(c.id)} className="rounded-lg border border-[var(--color-border)] px-2 py-1 text-xs font-semibold disabled:opacity-50">Retry failed</button>}</div>{campaignAnalytics[c.id]&&<p className="mt-2 w-full text-xs text-[var(--text-muted)]">Delivered {campaignAnalytics[c.id].delivered_count} · Pending {campaignAnalytics[c.id].pending_count} · Retry {campaignAnalytics[c.id].retry_count} · Bounced {campaignAnalytics[c.id].bounced_count} · Complaints {campaignAnalytics[c.id].complained_count} · Unsubscribed {campaignAnalytics[c.id].unsubscribed_count}</p>}</div>)}{!campaigns.length&&<p className="py-3 text-xs text-[var(--text-muted)]">No email campaigns have been sent.</p>}</div>
      </section>
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5"><h2 className="text-lg font-bold">Administrator security</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Recent sign-in records for platform administrators. Revoking sessions invalidates all existing tokens for that administrator.</p><div className="mt-3 divide-y divide-[var(--color-border)]">{securitySessions.slice(0,30).map(s=><div key={s.event_id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-xs"><div><strong>{s.email}</strong><p className="text-[var(--text-muted)]">{s.success?"Successful":"Failed"} · {s.method} · {s.ip_address||"IP unavailable"} · {new Date(s.created_at).toLocaleString()}</p><p className="max-w-xl truncate text-[var(--text-muted)]">{s.user_agent||"Client unavailable"}</p></div>{s.success&&<button disabled={busy===`session-${s.user_id}`} onClick={()=>void revokeAdminUserSessions(s.user_id,s.email)} className="rounded-lg border border-red-500/40 px-3 py-1.5 font-semibold text-red-700 disabled:opacity-50">Revoke all sessions</button>}</div>)}{!securitySessions.length&&<p className="py-3 text-xs text-[var(--text-muted)]">No administrator sign-in records yet.</p>}</div>
        <h3 className="mt-5 text-sm font-bold">Failed administrator sign-ins</h3><div className="mt-2 divide-y divide-[var(--color-border)]">{failedAdminLogins.slice(0,20).map(f=><p key={f.id} className="py-2 text-xs"><strong>{f.email}</strong> · {f.method} · {f.ip_address||"IP unavailable"} · {new Date(f.created_at).toLocaleString()}</p>)}{!failedAdminLogins.length&&<p className="py-2 text-xs text-[var(--text-muted)]">No failed administrator sign-ins have been recorded.</p>}</div>
      </section>
    </>}
    {error && <div role="alert" className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm">{error}</div>}{notice && <div role="status" className="mb-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">{notice}</div>}
    {loading ? <p className="text-sm text-[var(--text-muted)]">Loading platform records…</p> : <>
      <section className="mb-7 grid grid-cols-2 gap-3 lg:grid-cols-3">{([["Customers", overview?.customers], ["Active accounts", overview?.active_customers], ["Organisations", overview?.organizations], ["Active subscriptions", overview?.active_subscriptions], ["Pending payments", overview?.pending_payments], ["Failed webhooks", overview?.failed_webhooks]] as const).map(([label, value]) => <article key={label} className="rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4"><p className="text-xs text-[var(--text-muted)]">{label}</p><p className="mt-2 text-2xl font-extrabold tabular-nums">{value ?? "—"}</p></article>)}</section>
      <section className="mb-7 grid gap-4 xl:grid-cols-2">
        <article className="rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5">
          <h2 className="text-lg font-bold">Financial monitoring · last 90 days</h2>
          <p className="mt-1 text-xs text-[var(--text-muted)]">Confirmed paid transactions, grouped by currency. Amounts are not converted or combined.</p>
          <div className="mt-4 space-y-3">{financials?.revenue_by_currency.map((row) => <div key={row.currency} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] pb-3"><div><strong>{row.currency}</strong><p className="text-xs text-[var(--text-muted)]">{row.paid_transactions} successful payments</p></div><strong className="text-lg tabular-nums">{money(row.paid_amount_minor,row.currency)}</strong></div>)}{!financials?.revenue_by_currency.length && <p className="text-sm text-[var(--text-muted)]">No confirmed revenue in this period.</p>}</div>
          <h3 className="mt-5 text-sm font-bold">Refunds and chargebacks</h3>
          <p className="mt-1 text-xs text-[var(--text-muted)]">Provider-signed refund and dispute events. Open disputes are exposure, not confirmed losses.</p>
          <div className="mt-2 space-y-2">{financials?.payment_adjustments?.map((row) => <div key={`${row.type}-${row.status}-${row.currency}`} className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] py-2 text-sm"><div><strong className="capitalize">{row.type.replace("_"," ")} · {row.status}</strong><p className="text-xs text-[var(--text-muted)]">{row.events} events · {row.currency}</p></div><strong className="tabular-nums">{money(row.amount_minor,row.currency)}</strong></div>)}{!financials?.payment_adjustments?.length && <p className="text-xs text-[var(--text-muted)]">No refund or chargeback events recorded in this period.</p>}</div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">{financials?.refund_chargeback_note}</p>
          <h3 className="mt-4 text-sm font-bold">AI provider consumption</h3>
          <p className="mt-1 text-xs text-[var(--text-muted)]">Provider-reported token counts, grouped by model and feature.</p>
          <div className="mt-2 space-y-2">{financials?.ai_usage_by_model?.map((row) => <div key={`${row.provider}-${row.model}-${row.feature}`} className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] py-2 text-sm"><div><strong>{row.model}</strong><p className="text-xs text-[var(--text-muted)]">{row.provider} · {row.feature} · {row.events} requests</p></div><div className="text-right tabular-nums"><strong>{row.total_tokens.toLocaleString()} tokens</strong><p className="text-xs text-[var(--text-muted)]">{row.prompt_tokens.toLocaleString()} in / {row.completion_tokens.toLocaleString()} out</p></div></div>)}{!financials?.ai_usage_by_model?.length && <p className="text-xs text-[var(--text-muted)]">No provider token usage has been recorded yet.</p>}</div>
          <p className="mt-2 text-xs text-[var(--text-muted)]">{financials?.ai_cost_estimation?.note || "AI cost estimates require configured model pricing."}</p>
          <h3 className="mt-4 text-sm font-bold">Usage by feature</h3>{financials?.usage_by_metric.map((row) => <div key={row.metric} className="mt-2 flex justify-between text-sm"><span>{row.metric}</span><span className="tabular-nums">{row.quantity.toLocaleString()} ({row.events} events)</span></div>)}
          <p className="mt-4 rounded-lg bg-amber-500/10 p-3 text-xs text-amber-800">Profit is not yet calculated: provider fees, all operating invoices and overlapping refunds / disputes still require accounting reconciliation. {financials?.cost_tracking.reason}</p>
        </article>
        <article className="rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5"><h2 className="text-lg font-bold">Recent customer sign-ins</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Successful password sign-ins recorded from the time this telemetry was deployed.</p><div className="mt-3 space-y-2">{loginEvents.slice(0,10).map((event) => <div key={event.id} className="flex justify-between gap-3 border-b border-[var(--color-border)] py-2 text-xs"><div><strong>{event.full_name}</strong><p className="text-[var(--text-muted)]">{event.email} · {event.method}</p></div><time className="shrink-0 text-[var(--text-muted)]">{new Date(event.created_at).toLocaleString()}</time></div>)}{!loginEvents.length && <p className="text-sm text-[var(--text-muted)]">No sign-in events recorded yet.</p>}</div></article>
      </section>
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5">
        <h2 className="text-lg font-bold">Operating cost ledger</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Record verified invoices for hosting, AI providers, storage, email and other operating expenses. Amounts are entered in major currency units and stored in minor units.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <label className="text-xs font-semibold">Category<select value={costForm.category} onChange={e=>setCostForm({...costForm,category:e.target.value})} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"><option value="hosting">Hosting</option><option value="ai">AI provider</option><option value="image_video">Image / video</option><option value="storage">Storage / bandwidth</option><option value="email">Email / messaging</option><option value="other">Other</option></select></label>
          <label className="text-xs font-semibold">Provider<input value={costForm.provider} onChange={e=>setCostForm({...costForm,provider:e.target.value})} placeholder="e.g. Render, OpenAI" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"/></label>
          <label className="text-xs font-semibold">Description<input value={costForm.description} onChange={e=>setCostForm({...costForm,description:e.target.value})} placeholder="November hosting invoice" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"/></label>
          <label className="text-xs font-semibold">Amount<input type="number" min="0.01" step="0.01" value={costForm.amount} onChange={e=>setCostForm({...costForm,amount:e.target.value})} placeholder="0.00" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"/></label>
          <label className="text-xs font-semibold">Currency<select value={costForm.currency} onChange={e=>setCostForm({...costForm,currency:e.target.value})} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"><option value="NGN">NGN</option><option value="USD">USD</option><option value="EUR">EUR</option><option value="GBP">GBP</option></select></label>
          <label className="text-xs font-semibold">Period start<input type="date" value={costForm.period_start} onChange={e=>setCostForm({...costForm,period_start:e.target.value})} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"/></label>
          <label className="text-xs font-semibold">Period end<input type="date" value={costForm.period_end} onChange={e=>setCostForm({...costForm,period_end:e.target.value})} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] p-2 text-sm"/></label>
          <button type="button" disabled={busy==="cost-entry"} onClick={()=>void addCostEntry()} className="self-end rounded-xl bg-[var(--color-brand)] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{busy==="cost-entry"?"Saving…":"Record operating cost"}</button>
        </div>
        <div className="mt-5 space-y-2">{costEntries.slice(0,12).map(entry=><div key={entry.id} className="flex flex-wrap justify-between gap-2 border-b border-[var(--color-border)] py-2 text-sm"><div><strong>{entry.description}</strong><p className="text-xs text-[var(--text-muted)]">{entry.category} · {entry.provider} · {entry.period_start} to {entry.period_end}</p></div><strong>{money(entry.amount_minor,entry.currency)}</strong></div>)}{!costEntries.length&&<p className="text-sm text-[var(--text-muted)]">No operating costs have been entered yet.</p>}</div>
      </section>
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5"><h2 className="text-lg font-bold">Customer activity</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Organization activity records, including drafts, scheduling and other logged actions.</p><div className="mt-3 space-y-2">{platformActivity.slice(0,15).map((event) => <article key={event.id} className="flex flex-wrap justify-between gap-2 border-b border-[var(--color-border)] py-2 text-xs"><div><strong>{event.action}</strong><p className="text-[var(--text-muted)]">{event.actor_name} · {event.actor_email || "Account unavailable"} · {event.organization}</p><p className="mt-1">{event.summary}</p></div><time className="text-[var(--text-muted)]">{new Date(event.created_at).toLocaleString()}</time></article>)}{!platformActivity.length && <p className="text-sm text-[var(--text-muted)]">No organization activity has been recorded.</p>}</div></section>
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div><h2 className="text-lg font-bold">Top 10 customers</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Ranked by lifetime successful payments initiated by each customer. Only confirmed paid transactions count.</p></div>
          <div className="flex flex-wrap gap-2">
            <label className="text-xs text-[var(--text-muted)]">Currency<Select aria-label="Leaderboard currency" value={topCurrency} onChange={(e) => { setTopCurrency(e.target.value); }} className="mt-1 block rounded-xl border border-[var(--color-border)] bg-[var(--page)] px-3 py-2 text-sm text-[var(--text)]"><option value="NGN">NGN · Naira</option><option value="USD">USD · US dollar</option></Select></label>
            <label className="text-xs text-[var(--text-muted)]">Order<Select aria-label="Leaderboard sort order" value={topSort} onChange={(e) => { setTopSort(e.target.value); }} className="mt-1 block rounded-xl border border-[var(--color-border)] bg-[var(--page)] px-3 py-2 text-sm text-[var(--text)]"><option value="desc">Highest spend first</option><option value="asc">Lowest spend first</option></Select></label>
            <button type="button" onClick={() => void refresh(token, offset)} className="self-end rounded-xl border border-[var(--color-border)] px-3 py-2 text-sm font-semibold">Refresh</button>
          </div>
        </div>
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><thead><tr className="border-b border-[var(--color-border)] text-xs text-[var(--text-muted)]"><th className="p-3">Rank</th><th className="p-3">Customer</th><th className="p-3">Lifetime spend</th><th className="p-3">Successful payments</th><th className="p-3">Account</th></tr></thead><tbody>{topCustomers.map((customer) => <tr key={customer.user_id} className="border-b border-[var(--color-border)] last:border-0"><td className="p-3 font-extrabold tabular-nums">#{customer.rank}</td><td className="p-3"><strong>{customer.full_name}</strong><p className="text-xs text-[var(--text-muted)]">{customer.email || "No email address"}</p></td><td className="p-3 font-bold tabular-nums">{money(customer.total_spend_minor, customer.currency)}</td><td className="p-3 tabular-nums">{customer.successful_payment_count}</td><td className="p-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${customer.is_active ? "bg-emerald-500/10 text-emerald-700" : "bg-red-500/10 text-red-700"}`}>{customer.is_active ? "Active" : "Suspended"}</span></td></tr>)}</tbody></table>{topCustomers.length === 0 && <p className="p-6 text-center text-sm text-[var(--text-muted)]">No successful {topCurrency} payments have been recorded yet.</p>}</div>
        <p className="mt-3 text-xs text-[var(--text-muted)]">NGN and USD are ranked separately to avoid comparing unlike currencies without an exchange-rate conversion. Switching the order recalculates the top 10 for the selected currency.</p>
      </section>
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5"><div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-lg font-bold">Payment operations</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Configuration and recent provider activity. No secret keys are displayed.</p></div><div className="flex flex-wrap items-center gap-2"><button type="button" disabled={busy === "reconciliation"} onClick={() => void runReconciliation()} className="rounded-xl bg-[var(--color-brand)] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{busy === "reconciliation" ? "Checking payments…" : "Run reconciliation"}</button><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${billingOps?.paystack.mode === "test" ? "bg-amber-500/10 text-amber-700" : billingOps?.paystack.mode === "live" ? "bg-emerald-500/10 text-emerald-700" : "bg-slate-500/10 text-[var(--text-muted)]"}`}>Paystack: {billingOps?.paystack.mode ?? "unknown"} mode</span></div></div><div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-[var(--color-border)] p-3"><p className="text-xs text-[var(--text-muted)]">API credentials</p><strong className="text-sm">{billingOps?.paystack.credentials_configured ? "Configured" : "Missing"}</strong></div><div className="rounded-xl border border-[var(--color-border)] p-3"><p className="text-xs text-[var(--text-muted)]">Webhook signing secret</p><strong className="text-sm">{billingOps?.paystack.webhook_secret_configured ? "Configured" : "Missing"}</strong></div><div className="rounded-xl border border-[var(--color-border)] p-3"><p className="text-xs text-[var(--text-muted)]">Google Pay</p><strong className="text-sm">Paystack Checkout channel</strong></div></div><p className="mt-3 text-xs text-[var(--text-muted)]">{billingOps?.live_verification}</p><div className="mt-4 grid gap-4 lg:grid-cols-2"><div><h3 className="mb-2 text-sm font-bold">Recent transactions</h3>{billingOps?.transactions.slice(0,6).map((tx) => <div key={tx.reference} className="flex justify-between gap-2 border-b border-[var(--color-border)] py-2 text-xs"><span className="truncate">{tx.reference}<span className="block text-[var(--text-muted)]">{tx.plan_id} · {tx.provider}</span></span><span className="shrink-0 text-right">{money(tx.amount_minor,tx.currency)}<span className="block text-[var(--text-muted)]">{tx.status}</span></span></div>)}{!billingOps?.transactions.length && <p className="text-xs text-[var(--text-muted)]">No transactions recorded.</p>}</div><div><h3 className="mb-2 text-sm font-bold">Recent webhook events</h3>{billingOps?.webhooks.slice(0,6).map((event) => <div key={event.id} className="border-b border-[var(--color-border)] py-2 text-xs"><div className="flex justify-between gap-2"><strong>{event.event_type}</strong><span>{event.status}</span></div><p className="mt-1 break-all text-[var(--text-muted)]">{event.reference || "No transaction reference"}</p>{event.failure_message && <p className="mt-1 text-red-600">{event.failure_message}</p>}{(event.status === "failed") && <button type="button" disabled={busy === event.id} onClick={() => void retryWebhook(event.id)} className="mt-2 rounded-lg border border-[var(--color-border)] px-2.5 py-1.5 font-semibold disabled:opacity-50">{busy === event.id ? "Retrying…" : "Retry verification"}</button>}</div>)}{!billingOps?.webhooks.length && <p className="text-xs text-[var(--text-muted)]">No webhook events recorded.</p>}</div></div></section>
      <section className="mb-7 rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5"><div className="mb-3"><h2 className="text-lg font-bold">Platform administrator audit trail</h2><p className="mt-1 text-xs text-[var(--text-muted)]">Recent global account and billing operations performed by platform administrators.</p></div>{audits.length ? <div className="space-y-2">{audits.map((entry) => <article key={entry.id} className="rounded-xl border border-[var(--color-border)] p-3"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-sm">{entry.action}</strong><time className="text-xs text-[var(--text-muted)]">{new Date(entry.created_at).toLocaleString()}</time></div><p className="mt-1 text-xs text-[var(--text-muted)]">{entry.summary}</p></article>)}</div> : <p className="text-sm text-[var(--text-muted)]">No platform administration actions have been recorded yet.</p>}</section>
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-4 md:p-5"><div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-bold">Customer accounts</h2><p className="mt-1 text-xs text-[var(--text-muted)]">{data?.total ?? 0} matching accounts · select a customer to inspect details</p></div><div className="flex flex-wrap gap-2"><input aria-label="Search customers" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void refresh(token, 0); }} placeholder="Search name or email" className="min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--page)] px-3 py-2 text-sm"/><Select aria-label="Account status" value={status} onChange={(e) => { setStatus(e.target.value); }} className="rounded-xl border border-[var(--color-border)] bg-[var(--page)] px-3 py-2 text-sm"><option value="all">All accounts</option><option value="active">Active</option><option value="suspended">Suspended</option></Select><button type="button" onClick={() => void refresh(token, 0)} className="rounded-xl bg-[var(--color-brand)] px-4 py-2 text-sm font-bold text-white">Search</button></div></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left text-sm"><thead><tr className="border-b border-[var(--color-border)] text-xs text-[var(--text-muted)]"><th className="p-3">Customer</th><th className="p-3">Organisations</th><th className="p-3">Joined</th><th className="p-3">Status</th><th className="p-3">Details</th></tr></thead><tbody>{data?.items.map((customer) => <tr key={customer.id} className="border-b border-[var(--color-border)] last:border-0"><td className="p-3"><strong>{customer.full_name}</strong><p className="text-xs text-[var(--text-muted)]">{customer.email || "No email address"}</p></td><td className="p-3">{customer.organizations.length}</td><td className="p-3">{new Date(customer.created_at).toLocaleDateString()}</td><td className="p-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${customer.is_active ? "bg-emerald-500/10 text-emerald-700" : "bg-red-500/10 text-red-700"}`}>{customer.is_active ? "Active" : "Suspended"}</span></td><td className="p-3"><button onClick={() => void openCustomer(customer)} className="font-semibold text-[var(--color-brand)]">Inspect →</button></td></tr>)}</tbody></table>{data?.items.length === 0 && <p className="p-6 text-center text-sm text-[var(--text-muted)]">No matching customers.</p>}</div>
        <div className="mt-4 flex items-center justify-between text-xs text-[var(--text-muted)]"><span>Showing {data?.items.length ?? 0} of {data?.total ?? 0}</span><div className="flex gap-2"><button disabled={offset === 0} onClick={() => void refresh(token, Math.max(0, offset - 25))} className="rounded-lg border border-[var(--color-border)] px-3 py-2 disabled:opacity-40">Previous</button><button disabled={!data || offset + 25 >= data.total} onClick={() => void refresh(token, offset + 25)} className="rounded-lg border border-[var(--color-border)] px-3 py-2 disabled:opacity-40">Next</button></div></div>
      </section>
    </>}
    {selected && <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 md:items-center md:p-5" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelected(null); }}><section role="dialog" aria-modal="true" aria-labelledby="customer-title" className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-t-2xl border border-[var(--color-border)] bg-[var(--surface)] p-5 shadow-2xl md:rounded-2xl"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-[var(--color-brand)]">Customer record</p><h2 id="customer-title" className="mt-1 text-xl font-extrabold">{selected.full_name}</h2><p className="text-sm text-[var(--text-muted)]">{selected.email || "No email"} · {selected.email_verified ? "Email verified" : "Email not verified"}</p></div><button onClick={() => setSelected(null)} className="rounded-lg border border-[var(--color-border)] px-3 py-1.5">Close</button></div>
      <div className="my-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] p-3"><div><strong>Account access</strong><p className="text-xs text-[var(--text-muted)]">{selected.is_active ? "This customer can sign in." : "This customer is suspended."}</p></div><button disabled={busy === selected.id} onClick={() => void changeStatus(selected)} className={`rounded-xl px-4 py-2 text-sm font-bold text-white disabled:opacity-50 ${selected.is_active ? "bg-red-600" : "bg-emerald-600"}`}>{busy === selected.id ? "Saving…" : selected.is_active ? "Suspend account" : "Reactivate account"}</button></div>
      <section className="my-5 rounded-xl border border-[var(--color-border)] p-4">
        <h3 className="font-bold">Secure password recovery</h3>
        <p className="mt-1 text-xs text-[var(--text-muted)]">Send a one-time reset link only to this customer's existing verified email. You cannot view or set their password.</p>
        {!selected.email_verified ? <p className="mt-3 rounded-lg bg-amber-500/10 p-3 text-xs text-amber-800">This account has no verified email address. A separate manual identity-verification process is required.</p> : <>
          <label htmlFor="recovery-reason" className="mt-3 block text-xs font-semibold">Support reason (required)</label>
          <textarea id="recovery-reason" rows={2} maxLength={500} value={recoveryReason} onChange={(event) => setRecoveryReason(event.target.value)} placeholder="Describe the customer's recovery request and how ownership was confirmed…" className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--page)] p-3 text-sm" />
          <button type="button" disabled={busy === `recovery-${selected.id}` || recoveryReason.trim().length < 20 || !selected.is_active} onClick={() => void initiatePasswordRecovery(selected)} className="mt-3 rounded-xl bg-[var(--color-brand)] px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{busy === `recovery-${selected.id}` ? "Sending…" : "Send password reset link"}</button>
          {!selected.is_active && <p className="mt-2 text-xs text-[var(--text-muted)]">Reactivate the account before initiating recovery.</p>}
        </>}
      </section>
      <h3 className="mb-2 font-bold">Organisations and subscriptions</h3>{selected.organizations.length ? <div className="space-y-2">{selected.organizations.map((org) => <article key={org.id} className="rounded-xl border border-[var(--color-border)] p-3"><div className="flex flex-wrap justify-between gap-2"><strong>{org.name}</strong><span className="text-xs text-[var(--text-muted)]">{org.role} · {org.plan}</span></div><p className="mt-1 text-xs text-[var(--text-muted)]">{org.subscription ? `${org.subscription.status} · ${org.subscription.plan_id} · ${money(org.subscription.amount_minor, org.subscription.currency)} / ${org.subscription.billing_interval || "—"} · ${org.subscription.provider}` : "No subscription record"}</p></article>)}</div> : <p className="text-sm text-[var(--text-muted)]">No organisations found.</p>}
      <h3 className="mb-2 mt-5 font-bold">Connected social accounts</h3>{(selected as CustomerDetail & {social_accounts?:{id:string;provider:string;account_name:string;status:string;last_synced_at:string|null}[]}).social_accounts?.length ? (selected as CustomerDetail & {social_accounts:{id:string;provider:string;account_name:string;status:string;last_synced_at:string|null}[]}).social_accounts.map((account) => <article key={account.id} className="mb-2 flex justify-between rounded-xl border border-[var(--color-border)] p-3 text-sm"><div><strong>{account.provider} · {account.account_name}</strong><p className="text-xs text-[var(--text-muted)]">Last sync: {account.last_synced_at ? new Date(account.last_synced_at).toLocaleString() : "Not recorded"}</p></div><span>{account.status}</span></article>) : <p className="text-sm text-[var(--text-muted)]">No connected social accounts recorded.</p>}
      <h3 className="mb-2 mt-5 font-bold">Recent content activity</h3>{(selected as CustomerDetail & {recent_content?:{id:string;topic:string|null;status:string;content_preview:string;created_at:string}[]}).recent_content?.length ? (selected as CustomerDetail & {recent_content:{id:string;topic:string|null;status:string;content_preview:string;created_at:string}[]}).recent_content.map((item) => <article key={item.id} className="mb-2 rounded-xl border border-[var(--color-border)] p-3 text-sm"><div className="flex justify-between gap-2"><strong>{item.topic || "Untitled content"}</strong><span>{item.status}</span></div><p className="mt-1 text-xs text-[var(--text-muted)]">{item.content_preview}</p><time className="mt-1 block text-xs text-[var(--text-muted)]">{new Date(item.created_at).toLocaleString()}</time></article>) : <p className="text-sm text-[var(--text-muted)]">No saved content records found.</p>}
      <h3 className="mb-2 mt-5 font-bold">Recent login history</h3>{(selected as CustomerDetail & {login_history?:{method:string;created_at:string;user_agent:string|null}[]}).login_history?.map((entry,index) => <p key={index} className="mb-1 text-xs text-[var(--text-muted)]">{new Date(entry.created_at).toLocaleString()} · {entry.method} · {entry.user_agent || "Client not identified"}</p>)}
      <h3 className="mb-2 mt-5 font-bold">Recent payment transactions</h3>{selected.payment_transactions.length ? <div className="space-y-2">{selected.payment_transactions.map((tx) => <article key={tx.reference} className="flex flex-wrap justify-between gap-2 rounded-xl border border-[var(--color-border)] p-3 text-sm"><div><strong>{money(tx.amount_minor, tx.currency)}</strong><p className="text-xs text-[var(--text-muted)]">{tx.plan_id} · {tx.billing_interval} · {tx.provider}</p><p className="text-xs text-[var(--text-muted)]">{tx.reference}</p></div><div className="text-right"><span className="text-xs font-semibold">{tx.status}</span><p className="text-xs text-[var(--text-muted)]">{new Date(tx.created_at).toLocaleString()}</p></div></article>)}</div> : <p className="text-sm text-[var(--text-muted)]">No payment transactions initiated by this customer.</p>}</section></div>}
  </main>;
}
