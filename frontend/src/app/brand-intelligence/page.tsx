"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, getStoredOrganization, type AuthOrganization } from "@/lib/auth";
import { fetchSocialAccounts, type SocialAccount } from "@/lib/social";
import {
  createBrandAnalysis, enqueueSocialSync, fetchBrandAnalyses, fetchBrandObservations, fetchBrandSyncJobs, reviewBrandAnalysis,
  type BrandAnalysis, type BrandObservation, type BrandSyncJob,
} from "@/lib/brand-intelligence";

const button = "rounded-xl px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50";
const primary = `${button} bg-[var(--color-brand)] text-white`;
const secondary = `${button} border border-[var(--color-border)]`;

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export default function BrandIntelligencePage() {
  const router = useRouter();
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [observations, setObservations] = useState<BrandObservation[]>([]);
  const [analyses, setAnalyses] = useState<BrandAnalysis[]>([]);
  const [syncJobs, setSyncJobs] = useState<BrandSyncJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canManage = organization?.role === "owner" || organization?.role === "admin";

  const refresh = useCallback(async (token: string, orgId: string) => {
    const [socialRows, observationRows, analysisRows, jobRows] = await Promise.all([
      fetchSocialAccounts(token, orgId), fetchBrandObservations(token, orgId), fetchBrandAnalyses(token, orgId), fetchBrandSyncJobs(token, orgId),
    ]);
    setAccounts(socialRows);
    setObservations(observationRows);
    setAnalyses(analysisRows);
    setSyncJobs(jobRows);
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    const active = getStoredOrganization();
    if (!token || !active) { router.replace("/login"); return; }
    setOrganization(active);
    let cancelled = false;
    void refresh(token, active.id).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : "Brand Intelligence could not be loaded.");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refresh, router]);

  // Poll only while this workspace has active jobs; terminal results remain visible in history.
  useEffect(() => {
    if (!organization || !syncJobs.some((job) => job.status === "queued" || job.status === "running")) return;
    const timer = window.setInterval(() => {
      const token = getAccessToken();
      if (!token) return;
      void fetchBrandSyncJobs(token, organization.id)
        .then((jobs) => {
          const hadActiveJobs = syncJobs.some((job) => job.status === "queued" || job.status === "running");
          const hasActiveJobs = jobs.some((job) => job.status === "queued" || job.status === "running");
          setSyncJobs(jobs);
          if (hadActiveJobs && !hasActiveJobs) {
            void refresh(token, organization.id).catch(() => { /* Keep the completed job visible if data refresh fails. */ });
          }
        })
        .catch(() => { /* Keep the last known job state; the next poll can recover. */ });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [organization, syncJobs, refresh]);

  async function run(label: string, action: (token: string, orgId: string) => Promise<void>) {
    const token = getAccessToken();
    if (!token || !organization) { router.replace("/login"); return; }
    setBusy(label); setError(""); setNotice("");
    try { await action(token, organization.id); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "The request could not be completed."); }
    finally { setBusy(""); }
  }

  function sync(account: SocialAccount) {
    void run(`sync-${account.id}`, async (token, orgId) => {
      const job = await enqueueSocialSync(token, orgId, account.id);
      setNotice(job.status === "queued" || job.status === "running"
        ? `${account.provider} synchronization ${job.status === "queued" ? "queued" : "is already running"}. This page will update its status automatically.`
        : `Synchronization request returned ${job.status}.`);
      const jobs = await fetchBrandSyncJobs(token, orgId);
      setSyncJobs(jobs);
    });
  }

  function analyze(method: "ai" | "rules" = "ai") {
    void run(method === "rules" ? "analyze-rules" : "analyze", async (token, orgId) => {
      await createBrandAnalysis(token, orgId, method);
      setNotice("A new brand analysis is ready for review. It has not changed your confirmed business profile.");
      await refresh(token, orgId);
    });
  }

  function review(analysis: BrandAnalysis, decision: "approved" | "rejected") {
    void run(`${decision}-${analysis.id}`, async (token, orgId) => {
      await reviewBrandAnalysis(token, orgId, analysis.id, decision);
      setNotice(`Analysis ${decision}. Your confirmed business profile remains unchanged.`);
      await refresh(token, orgId);
    });
  }

  return <main className="mx-auto max-w-6xl px-4 py-7 text-[var(--color-text)] sm:px-6">
    <Link href="/social-accounts" className="text-sm font-semibold text-[var(--color-brand)]">← Social accounts</Link>
    <header className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-xs font-bold tracking-[0.18em] text-[var(--color-brand)]">EVIDENCE-BASED BRAND CONTEXT</p><h1 className="mt-2 text-3xl font-extrabold">Brand Intelligence</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-muted)]">Review content retrieved from connected social accounts and generate suggestions about your brand voice. Social observations never overwrite the business facts you confirmed.</p></div>
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={!canManage || loading || observations.length === 0 || !!busy} onClick={() => analyze("ai")} className={primary}>{busy === "analyze" ? "Analyzing…" : "Analyze with AI"}</button>
        <button type="button" disabled={!canManage || loading || observations.length === 0 || !!busy} onClick={() => analyze("rules")} className={secondary}>{busy === "analyze-rules" ? "Analyzing…" : "Analyze without AI"}</button>
      </div>
    </header>
    {error && <p role="alert" className="mt-5 rounded-xl border border-[var(--color-danger)]/30 p-3 text-sm text-[var(--color-danger)]">{error}</p>}
    {notice && <p role="status" className="mt-5 rounded-xl border border-[var(--color-brand)]/30 p-3 text-sm">{notice}</p>}

    <section className="mt-7 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-bold">Connected social accounts</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Queue a durable background sync for up to 20 recent items. Jobs continue independently of this page and their status is shown below.</p></div><Link href="/social-accounts" className="text-sm font-semibold text-[var(--color-brand)]">Manage connections →</Link></div>
      {loading ? <p className="py-6 text-sm text-[var(--color-text-muted)]">Loading connected accounts…</p> : accounts.length === 0 ? <p className="mt-4 rounded-xl border border-dashed border-[var(--color-border)] p-6 text-sm text-[var(--color-text-muted)]">Connect an Instagram professional account, Facebook Page, TikTok account, or YouTube channel with the required read permission to retrieve recent posts and videos. You can still create content using your business profile without connecting social accounts.</p> : <div className="mt-4 divide-y divide-[var(--color-border)]">{accounts.map((account) => <article key={account.id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-semibold">{account.account_name}</p><p className="mt-1 text-xs capitalize text-[var(--color-text-muted)]">{account.provider} · {account.status} · {account.last_synced_at ? `Last synced ${new Date(account.last_synced_at).toLocaleString()}` : "Not synchronized yet"}</p></div><button type="button" disabled={!canManage || !(["instagram", "facebook", "tiktok", "youtube"].includes(account.provider)) || !!busy} onClick={() => sync(account)} className={secondary}>{busy === `sync-${account.id}` ? "Queuing…" : ["instagram", "facebook", "tiktok", "youtube"].includes(account.provider) ? "Queue sync" : "Sync unavailable"}</button></article>)}</div>}
    </section>

    <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-bold">Synchronization history</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Background jobs are processed by the server. Active jobs refresh automatically every five seconds.</p></div><span className="text-xs text-[var(--color-text-muted)]">{syncJobs.length} recent jobs</span></div>
      {syncJobs.length === 0 ? <p className="mt-4 rounded-xl border border-dashed border-[var(--color-border)] p-5 text-sm text-[var(--color-text-muted)]">No synchronization jobs yet. Queue a sync from a connected account above.</p> : <div className="mt-4 space-y-3">{syncJobs.map((job) => {
        const account = accounts.find((item) => item.id === job.social_account_id);
        const active = job.status === "queued" || job.status === "running";
        const statusClass = job.status === "succeeded" ? "text-[var(--color-success)]" : job.status === "failed" ? "text-[var(--color-danger)]" : job.status === "running" ? "text-[var(--color-info)]" : "text-[var(--color-warning)]";
        return <article key={job.id} className="rounded-xl border border-[var(--color-border)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="font-semibold">{account?.account_name ?? `${account?.provider ?? "Social"} account`}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">Requested {new Date(job.created_at).toLocaleString()} · Attempt {job.attempts}/{job.max_attempts}</p></div><span className={`text-xs font-bold uppercase ${statusClass}`}>{job.status}</span></div>
          {job.result && <p className="mt-2 text-sm text-[var(--color-text-muted)]">{job.result.retrieved} retrieved · {job.result.inserted} new · {job.result.updated} updated</p>}
          {job.error_message && <p role="status" className="mt-2 rounded-lg border border-[var(--color-danger)]/25 p-2 text-xs leading-5 text-[var(--color-danger)]">{job.error_message}</p>}
          {active && <p className="mt-2 text-xs text-[var(--color-text-muted)]">{job.status === "queued" ? "Waiting for a worker…" : "The provider is being contacted…"}</p>}
          {job.status === "failed" && canManage && account && <button type="button" disabled={!!busy} onClick={() => sync(account)} className={`${secondary} mt-3`}>{busy === `sync-${account.id}` ? "Queuing…" : "Try again"}</button>}
        </article>;
      })}</div>}
    </section>

    <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 sm:p-6"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-bold">Observed posts</h2><span className="text-xs text-[var(--color-text-muted)]">{observations.length} shown</span></div>
      {loading ? <p className="py-6 text-sm text-[var(--color-text-muted)]">Loading observations…</p> : observations.length === 0 ? <p className="mt-4 rounded-xl border border-dashed border-[var(--color-border)] p-6 text-sm text-[var(--color-text-muted)]">No posts have been imported. Start an Instagram, Facebook, TikTok, or YouTube sync to collect up to 20 recent posts or videos.</p> : <div className="mt-4 space-y-3">{observations.map((post) => <article key={post.id} className="rounded-xl border border-[var(--color-border)] p-4"><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-semibold uppercase tracking-wide text-[var(--color-brand)]">{post.provider} · {String(post.provenance?.method ?? "unknown")}</span><span className="text-xs text-[var(--color-text-muted)]">{post.published_at ? new Date(post.published_at).toLocaleString() : "Date unavailable"}</span></div><p className="mt-2 whitespace-pre-wrap text-sm leading-6">{post.post_text || "No caption was provided by the platform."}</p>{post.permalink && <a href={post.permalink} target="_blank" rel="noreferrer" className="mt-3 inline-block text-xs font-semibold text-[var(--color-brand)]">View original post ↗</a>}</article>)}</div>}
    </section>

    <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 sm:p-6"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-bold">Analysis proposals</h2><span className="text-xs text-[var(--color-text-muted)]">Approval required</span></div>
      {loading ? <p className="py-6 text-sm text-[var(--color-text-muted)]">Loading analyses…</p> : analyses.length === 0 ? <p className="mt-4 rounded-xl border border-dashed border-[var(--color-border)] p-6 text-sm text-[var(--color-text-muted)]">No analyses yet. Sync posts, then select “Analyze recent posts”.</p> : <div className="mt-4 space-y-4">{analyses.map((analysis) => <article key={analysis.id} className="rounded-xl border border-[var(--color-border)] p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Brand voice proposal</h3><span className="rounded-full bg-[var(--color-page)] px-3 py-1 text-xs font-semibold capitalize">{analysis.status}</span></div>{analysis.proposal.method === "rules"
          ? <p className="mt-3 text-sm leading-6">Rule-based summary of {String(analysis.proposal.posts_analyzed ?? analysis.source_observation_ids.length)} posts. No AI model was used, so no brand voice is proposed. Evidence level: <strong>{String(analysis.proposal.evidence_level ?? "initial").replace("_", " ")}</strong>.</p>
          : <p className="mt-3 text-sm leading-6">{typeof analysis.proposal.proposed_voice === "string" && analysis.proposal.proposed_voice ? analysis.proposal.proposed_voice : "No proposed voice was returned."}</p>}<div className="mt-3 grid gap-3 sm:grid-cols-2"><div><p className="text-xs font-bold text-[var(--color-text-muted)]">TOPICS</p><p className="mt-1 text-sm">{strings(analysis.proposal.topics).join(", ") || "Not identified"}</p></div><div><p className="text-xs font-bold text-[var(--color-text-muted)]">TONE</p><p className="mt-1 text-sm">{strings(analysis.proposal.tone).join(", ") || "Not identified"}</p></div><div><p className="text-xs font-bold text-[var(--color-text-muted)]">HASHTAGS</p><p className="mt-1 text-sm">{strings(analysis.proposal.hashtags).join(" ") || "Not identified"}</p></div><div><p className="text-xs font-bold text-[var(--color-text-muted)]">EVIDENCE</p><p className="mt-1 text-sm">{analysis.source_observation_ids.length} source posts · {String(analysis.proposal.confidence ?? "unspecified")} confidence</p></div></div>
        {analysis.proposal.method === "rules" && (strings(analysis.proposal.writing_patterns).length > 0 || strings(analysis.proposal.suggestions).length > 0) && <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {strings(analysis.proposal.writing_patterns).length > 0 && <div><p className="text-xs font-bold text-[var(--color-text-muted)]">WRITING PATTERNS</p><ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{strings(analysis.proposal.writing_patterns).map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
          {strings(analysis.proposal.suggestions).length > 0 && <div><p className="text-xs font-bold text-[var(--color-text-muted)]">SUGGESTIONS</p><ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{strings(analysis.proposal.suggestions).map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
        </div>}
        {analysis.conflicts.length > 0 && <div className="mt-4 rounded-xl border border-[var(--color-danger)]/30 p-3"><p className="text-sm font-semibold">Potential conflicts with confirmed business information</p>{analysis.conflicts.map((conflict, index) => <p key={index} className="mt-2 text-xs leading-5">{String(conflict.explanation ?? conflict.field ?? "Review this discrepancy")}</p>)}</div>}
        {analysis.status === "pending" && canManage && <div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={!!busy} onClick={() => review(analysis, "approved")} className={primary}>{busy === `approved-${analysis.id}` ? "Saving…" : "Approve proposal"}</button><button type="button" disabled={!!busy} onClick={() => review(analysis, "rejected")} className={secondary}>{busy === `rejected-${analysis.id}` ? "Saving…" : "Reject proposal"}</button></div>}
        <p className="mt-3 text-xs text-[var(--color-text-muted)]">Created {new Date(analysis.created_at).toLocaleString()} · {analysis.proposal.method === "rules" ? "Rule-based (no AI model)" : `Model ${analysis.model ?? "not specified"}`}. Approval records your decision; it does not automatically rewrite your confirmed profile.</p>
      </article>)}</div>}
    </section>
  </main>;
}
