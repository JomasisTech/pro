"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, getStoredOrganization, type AuthOrganization } from "@/lib/auth";
import {
  disconnectSocialAccount,
  fetchSocialAccounts,
  fetchSocialProviders,
  startFacebookConnection,
  startInstagramConnection,
  startTikTokConnection,
  startYouTubeConnection,
  type SocialAccount,
  type SocialProvider,
} from "@/lib/social";

type PlatformKey = "facebook" | "instagram" | "tiktok" | "youtube";

const platformDetails: Record<PlatformKey, { mark: string; category: string; accent: string }> = {
  facebook: { mark: "f", category: "Pages", accent: "platform-mark-facebook" },
  instagram: { mark: "◎", category: "Professional accounts", accent: "platform-mark-instagram" },
  tiktok: { mark: "♪", category: "Short-form video", accent: "platform-mark-tiktok" },
  youtube: { mark: "▶", category: "Video channels", accent: "platform-mark-youtube" },
};

function isPlatformKey(key: string): key is PlatformKey {
  return Object.prototype.hasOwnProperty.call(platformDetails, key);
}

function PlatformMark({ platform }: { platform: string }) {
  const details = isPlatformKey(platform) ? platformDetails[platform] : null;
  return (
    <span aria-hidden="true" className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/20 text-xl font-bold text-white shadow-sm ${details?.accent ?? "bg-[var(--color-brand-solid)]"}`}>
      {details?.mark ?? platform.slice(0, 1).toUpperCase()}
    </span>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "Connected", connected: "Connected", expired: "Reconnect required",
    revoked: "Access revoked", error: "Attention required", pending: "Pending",
  };
  return labels[status.toLowerCase()] ?? status.replaceAll("_", " ");
}

export default function SocialAccountsPage() {
  const router = useRouter();
  const [org, setOrg] = useState<AuthOrganization | null>(null);
  const [providers, setProviders] = useState<SocialProvider[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [connecting, setConnecting] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canManage = org?.role === "owner" || org?.role === "admin";

  const refresh = useCallback(async (token: string, active: AuthOrganization) => {
    const [providerRows, accountRows] = await Promise.all([
      fetchSocialProviders(token, active.id),
      fetchSocialAccounts(token, active.id),
    ]);
    setProviders(providerRows);
    setAccounts(accountRows);
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    const active = getStoredOrganization();
    if (!token || !active) {
      router.replace("/login");
      return;
    }
    setOrg(active);
    void refresh(token, active)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Social accounts could not be loaded."))
      .finally(() => setLoading(false));
  }, [refresh, router]);

  async function reloadAccounts() {
    if (!org) return;
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setRefreshing(true);
    setError("");
    setNotice("");
    try {
      await refresh(token, org);
      setNotice("Social account information is up to date.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Social accounts could not be refreshed.");
    } finally {
      setRefreshing(false);
    }
  }

  async function connect(platform: PlatformKey) {
    if (!canManage || !org || connecting) return;
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setConnecting(platform);
    setError("");
    setNotice("");
    try {
      const startConnection = {
        facebook: startFacebookConnection,
        instagram: startInstagramConnection,
        tiktok: startTikTokConnection,
        youtube: startYouTubeConnection,
      }[platform];
      const authorizationUrl = await startConnection(token, org.id);
      window.location.assign(authorizationUrl);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `${platformDetails[platform].category} connection could not be started.`);
      setConnecting("");
    }
  }

  async function disconnect(account: SocialAccount) {
    if (!canManage || !org || busyId) return;
    if (!window.confirm(`Disconnect ${account.account_name}?`)) return;
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setBusyId(account.id);
    setError("");
    setNotice("");
    try {
      await disconnectSocialAccount(token, org.id, account.id);
      setAccounts((current) => current.filter((item) => item.id !== account.id));
      setNotice(`${account.account_name} has been disconnected.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not disconnect this account.");
    } finally {
      setBusyId("");
    }
  }

  const connectedCount = accounts.length;
  const availableCount = providers.filter((provider) => provider.connection_available && isPlatformKey(provider.key)).length;

  return (
    <main className="min-h-screen bg-[var(--color-page)] px-4 pb-12 pt-7 text-[var(--color-text)] sm:px-6 sm:pt-9">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-medium text-[var(--color-text-muted)] transition hover:text-[var(--color-text)]">
            <span aria-hidden="true">←</span> Back to overview
          </Link>
        </div>

        <header className="flex flex-col gap-5 border-b border-[var(--color-border)] pb-7 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-brand)]">Publishing workspace</p>
            <h1 className="mt-2 text-[2rem] font-semibold tracking-[-0.035em] sm:text-4xl">Social accounts</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-muted)] sm:text-base">
              Manage the channels your team uses to publish content. Connect accounts through each platform&apos;s official authorization process; your social passwords are never requested or stored here.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => void reloadAccounts()} disabled={loading || refreshing} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3.5 text-sm font-medium transition hover:bg-[var(--color-surface-raised)] disabled:cursor-wait disabled:opacity-60">
              <svg aria-hidden="true" viewBox="0 0 20 20" className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} fill="none"><path d="M16.2 8A6.4 6.4 0 0 0 5.1 4.8L3.5 6.4M3.5 6.4V2.9m0 3.5H7M3.8 12a6.4 6.4 0 0 0 11.1 3.2l1.6-1.6m0 0v3.5m0-3.5H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
              {refreshing ? "Refreshing" : "Refresh"}
            </button>
            <Link href="/content" className="inline-flex min-h-10 items-center justify-center rounded-lg bg-[var(--color-brand-solid)] px-4 text-sm font-semibold text-white shadow-sm transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-brand)]">Create content</Link>
          </div>
        </header>

        {(error || notice) && (
          <div role={error ? "alert" : "status"} className={`mt-5 flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${error ? "border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] text-[var(--color-danger)]" : "border-[var(--color-success)]/30 bg-[var(--color-success-soft)] text-[var(--color-text)]"}`}>
            <span>{error || notice}</span>
            <button type="button" aria-label="Dismiss message" onClick={() => { setError(""); setNotice(""); }} className="shrink-0 rounded p-0.5 opacity-70 transition hover:opacity-100">×</button>
          </div>
        )}

        <section aria-label="Connection summary" className="mt-6 grid gap-3 sm:grid-cols-3">
          {[
            { label: "Connected accounts", value: connectedCount },
            { label: "Platforms supported", value: providers.length },
            { label: "Ready to connect", value: availableCount },
          ].map((item) => (
            <div key={item.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
              <p className="text-xs font-medium text-[var(--color-text-muted)]">{item.label}</p>
              <p className="mt-1 text-2xl font-semibold tracking-tight">{loading ? "—" : item.value}</p>
            </div>
          ))}
        </section>

        <section className="mt-9">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Available platforms</h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">Choose a channel to authorize for this workspace.</p>
            </div>
            <span className="text-xs text-[var(--color-text-muted)]">{canManage ? "Workspace administrators can manage connections" : "Contact a workspace administrator to manage connections"}</span>
          </div>

          {loading ? (
            <div className="grid gap-3 md:grid-cols-2">{[0, 1, 2, 3].map((item) => <div key={item} className="h-36 animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]" />)}</div>
          ) : providers.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-12 text-center">
              <p className="font-semibold">No platforms are available yet</p>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--color-text-muted)]">Platform connection options will appear here when they are enabled for this deployment.</p>
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {providers.map((provider) => {
                // Keep the validated key itself so TypeScript can safely index
                // platformDetails and the connect handler without widening to string.
                const platformKey = isPlatformKey(provider.key) ? provider.key : null;
                const knownPlatform = platformKey !== null;
                const ready = provider.connection_available && knownPlatform;
                const isConnecting = connecting === provider.key;
                const connectedForProvider = accounts.filter((account) => account.provider.toLowerCase() === provider.key.toLowerCase()).length;
                return (
                  <article key={provider.key} className="flex min-h-40 flex-col justify-between rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 transition-colors hover:border-[var(--color-brand)]/40 sm:p-5">
                    <div className="flex items-start gap-3">
                      <PlatformMark platform={provider.key} />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold">{provider.name}</h3>
                          <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[11px] font-semibold ${ready ? "bg-[var(--color-success-soft)] text-[var(--color-success)]" : "bg-[var(--color-page)] text-[var(--color-text-muted)]"}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${ready ? "bg-[var(--color-success)]" : "bg-[var(--color-text-muted)]"}`} />
                            {ready ? "Available" : "Setup required"}
                          </span>
                        </div>
                        <p className="mt-1 text-xs font-medium text-[var(--color-text-muted)]">{platformKey ? platformDetails[platformKey].category : "Social channel"}</p>
                        <p className="mt-2 text-sm leading-5 text-[var(--color-text-muted)]">{provider.description}</p>
                      </div>
                    </div>
                    <div className="mt-4 flex items-center justify-between gap-3 border-t border-[var(--color-border)] pt-3">
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {connectedForProvider > 0 ? `${connectedForProvider} account${connectedForProvider === 1 ? "" : "s"} connected` : ready ? "Not connected" : "Awaiting administrator setup"}
                      </span>
                      <button type="button" disabled={!ready || !canManage || !knownPlatform || Boolean(connecting)} onClick={() => { if (platformKey) void connect(platformKey); }} title={!knownPlatform ? "This provider does not yet have a connection flow in the application." : !ready ? "Provider authorization is not configured yet." : !canManage ? "Only workspace owners and admins can connect accounts." : `Authorize with ${provider.name}`} className="inline-flex min-h-9 min-w-24 items-center justify-center rounded-lg bg-[var(--color-brand-solid)] px-3 text-xs font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:bg-[var(--color-page)] disabled:text-[var(--color-text-muted)] disabled:shadow-none">
                        {isConnecting ? "Opening…" : "Connect"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="mt-10">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Connected accounts</h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">Accounts authorized to publish for this workspace.</p>
            </div>
            {!loading && accounts.length > 0 && <span className="text-xs font-medium text-[var(--color-text-muted)]">{accounts.length} total</span>}
          </div>
          {loading ? (
            <div className="h-28 animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]" />
          ) : accounts.length === 0 ? (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-10 text-center sm:py-12">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--color-page)] text-[var(--color-text-muted)]"><svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6" fill="none"><path d="M8 12h8m-4-4v8m9-4a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg></div>
              <p className="mt-3 font-semibold">No accounts connected</p>
              <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-[var(--color-text-muted)]">Connect one of the available platforms above. Once authorized, your account will appear here and can be used in supported publishing workflows.</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
              <ul className="divide-y divide-[var(--color-border)]">
                {accounts.map((account) => {
                  const status = account.status.toLowerCase();
                  const healthy = status === "active" || status === "connected";
                  return (
                    <li key={account.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                      <div className="flex min-w-0 items-center gap-3">
                        <PlatformMark platform={account.provider.toLowerCase()} />
                        <div className="min-w-0">
                          <p className="truncate font-semibold">{account.account_name}</p>
                          <p className="mt-0.5 text-xs capitalize text-[var(--color-text-muted)]">{account.provider.replaceAll("_", " ")}{account.account_type ? ` · ${account.account_type.replaceAll("_", " ")}` : ""}</p>
                          <p className="mt-1 text-xs text-[var(--color-text-muted)]">Connected {formatDate(account.connected_at)}{account.last_synced_at ? ` · Last synced ${formatDate(account.last_synced_at)}` : ""}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${healthy ? "bg-[var(--color-success-soft)] text-[var(--color-success)]" : "bg-[var(--color-warning)]/10 text-[var(--color-warning)]"}`}>{statusLabel(account.status)}</span>
                        {canManage && <button type="button" disabled={busyId === account.id || Boolean(busyId)} onClick={() => void disconnect(account)} className="min-h-9 rounded-lg border border-[var(--color-border)] px-3 text-xs font-semibold text-[var(--color-text-muted)] transition hover:border-[var(--color-danger)]/40 hover:text-[var(--color-danger)] disabled:cursor-wait disabled:opacity-60">{busyId === account.id ? "Disconnecting…" : "Disconnect"}</button>}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </section>

        <aside className="mt-8 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--color-brand-solid)]/10 text-[var(--color-brand)]"><svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none"><path d="M12 16v-4m0-4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg></span>
            <div>
              <h2 className="text-sm font-semibold">About social connections</h2>
              <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">AutoBizPro uses official platform authorization. Instagram connections are for professional accounts; TikTok publishing depends on the required scope approval and app review. Facebook Pages currently support text and link posts, with photo and video publishing planned as a later enhancement. YouTube channels support the available video publishing workflow. Available actions depend on each platform&apos;s permissions and your account eligibility.</p>
            </div>
          </div>
        </aside>

        <nav aria-label="Related workspace tools" className="mt-8 flex flex-wrap gap-x-5 gap-y-3 border-t border-[var(--color-border)] pt-5 text-sm">
          <Link href="/brand-intelligence" className="font-medium text-[var(--color-brand)] hover:underline">Brand Intelligence</Link>
          <Link href="/profile" className="font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text)]">Business profile</Link>
          <Link href="/calendar" className="font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text)]">Content calendar</Link>
        </nav>
      </div>
    </main>
  );
}
