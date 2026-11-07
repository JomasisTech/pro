"use client";

import { Select } from "@/components/select";
import Link from "next/link";
import "./dashboard.css";
import { FormEvent, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  AuthUser,
  AuthOrganization,
  clearAuthSession,
  signOutAccount,
  createOrganization,
  fetchCurrentUser,
  fetchMyOrganizations,
  getAccessToken,
  getStoredOrganization,
  hasPlaceholderName,
  saveActiveOrganization,
} from "@/lib/auth";
import { ProfileCompletionPrompt } from "@/components/profile-completion-prompt";
import { NavIcon } from "@/components/app-chrome";
import { fetchDrafts, fetchUsage, type Draft, type Usage } from "@/lib/content";
import { fetchActivity, type ActivityEntry } from "@/lib/activity";
import { RANGE_OPTIONS, buildSeries, computeStats, describeTrend, isFailed, isPublished, platformBreakdown, type RangeDays } from "@/lib/dashboard-metrics";
import { ActivityList, EmptyState, Icon, KpiCard, Panel, PerformanceChart, PlanUsage, PlatformBadge, PlatformList, platformMeta } from "@/components/dashboard-sections";
import { fetchSocialAccounts, fetchCalendar, type SocialAccount, type CalendarItem } from "@/lib/social";
import { LeadsDiscoveryCard } from "@/components/leads-discovery-card";

const navigation = [
  { label: "Home", href: "/", icon: "home" },
  { label: "Social Media", href: "/social-accounts", icon: "share" },
  { label: "Brand Intelligence", href: "/brand-intelligence", icon: "sparkle" },
  { label: "Leads", href: "/leads", icon: "users" },
  { label: "Content Calendar", href: "/calendar", icon: "calendar" },
  { label: "Content Studio", href: "/content", icon: "edit" },
  { label: "TikTok Publishing", href: "/tiktok-publish", icon: "video" },
  { label: "Facebook Publishing", href: "/facebook-publish", icon: "facebook" },
  { label: "YouTube Publishing", href: "/youtube-publish", icon: "play" },
  { label: "Business Profile", href: "/profile", icon: "building" },
  { label: "Products & Services", href: "/products", icon: "package" },
  { label: "Activity Log", href: "/activity", icon: "activity" },
  { label: "Workspace Settings", href: "/workspace", icon: "settings" },
  { label: "Billing", href: "/billing", icon: "credit-card" },
  { label: "Account Security", href: "/security", icon: "lock" },
];

export default function Home() {
  const router = useRouter();
  const pathname = usePathname();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [authChecked, setAuthChecked] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [organizations, setOrganizations] = useState<AuthOrganization[]>([]);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [calendarItems, setCalendarItems] = useState<CalendarItem[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [usageFailed, setUsageFailed] = useState(false);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [range, setRange] = useState<RangeDays>(30);
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState("");
  const [workspaceSearch, setWorkspaceSearch] = useState("");
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  const mobileNavRef = useRef<HTMLElement>(null);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMobileMoreOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!switcherOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSwitcherOpen(false);
        profileMenuRef.current?.querySelector<HTMLButtonElement>(".bp-profile-trigger")?.focus();
      }
    };
    const closeOutside = (event: PointerEvent) => {
      if (!profileMenuRef.current?.contains(event.target as Node)) setSwitcherOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOutside);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeOutside);
    };
  }, [switcherOpen]);

  useEffect(() => {
    if (!mobileMoreOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileMoreOpen(false); };
    const closeOutside = (event: PointerEvent) => { if (!mobileNavRef.current?.contains(event.target as Node)) setMobileMoreOpen(false); };
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOutside);
    return () => { document.removeEventListener("keydown", closeOnEscape); document.removeEventListener("pointerdown", closeOutside); };
  }, [mobileMoreOpen]);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("bizpilotpro-theme") ?? window.localStorage.getItem("autobizpro-theme");
    const initialTheme = savedTheme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = initialTheme;
    setTheme(initialTheme);

    let cancelled = false;
    async function verifySession() {
      const token = getAccessToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      try {
        const [user, memberships] = await Promise.all([fetchCurrentUser(token), fetchMyOrganizations(token)]);
        if (cancelled) return;
        const savedId = getStoredOrganization()?.id;
        const active = memberships.find((item) => item.id === savedId) ?? memberships[0] ?? null;
        if (active) saveActiveOrganization(active);
        if (cancelled) return;
        setCurrentUser(user);
        setOrganizations(memberships);
        setOrganization(active);
        setDataLoading(Boolean(active));
        setAuthChecked(true);
      } catch {
        if (cancelled) return;
        clearAuthSession();
        router.replace("/login");
      }
    }
    void verifySession();
    return () => { cancelled = true; };
  }, [router]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token || !organization) return;
    let cancelled = false;
    setDataLoading(true);
    setDataError("");
    setDrafts([]);
    setAccounts([]);
    setCalendarItems([]);
    setUsage(null);
    setUsageFailed(false);
    setActivity([]);
    Promise.all([fetchDrafts(token, organization.id), fetchSocialAccounts(token, organization.id), fetchCalendar(token, organization.id)])
      .then(([draftRows, accountRows, calendarRows]) => {
        if (cancelled) return;
        setDrafts(draftRows);
        setAccounts(accountRows.filter((account) => account.status === "connected"));
        setCalendarItems(calendarRows);
      })
      .catch((error) => {
        if (!cancelled) setDataError(error instanceof Error ? error.message : "Workspace information could not be loaded.");
      })
      .finally(() => { if (!cancelled) setDataLoading(false); });
    // Secondary panels load independently so one failure never blanks the dashboard.
    fetchUsage(token, organization.id).then((value) => { if (!cancelled) setUsage(value); }).catch(() => { if (!cancelled) setUsageFailed(true); });
    fetchActivity(token, organization.id, 6).then((rows) => { if (!cancelled) setActivity(rows); }).catch(() => { /* activity is optional */ });
    return () => { cancelled = true; };
  }, [organization]);

  function chooseOrganization(next: AuthOrganization) {
    saveActiveOrganization(next);
    setDataLoading(true);
    setDrafts([]);
    setAccounts([]);
    setCalendarItems([]);
    setDataError("");
    setOrganization(next);
    setSwitcherOpen(false);
    setCreating(false);
  }

  async function handleCreateWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getAccessToken();
    if (!token) { router.replace("/login"); return; }
    setCreateError("");
    setCreateBusy(true);
    try {
      const created = await createOrganization(token, newName.trim());
      setOrganizations((current) => [...current, created]);
      chooseOrganization(created);
      setNewName("");
      router.push("/onboarding");
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Couldn't create the workspace. Try again.");
    } finally {
      setCreateBusy(false);
    }
  }

  async function signOut() {
    await signOutAccount();
    router.replace("/login");
  }

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("bizpilotpro-theme", nextTheme);
    setTheme(nextTheme);
  }

  const namedUser = hasPlaceholderName(currentUser) ? null : currentUser;
  const initials = namedUser?.full_name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "BP";

  if (!authChecked) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--color-page)] px-5 text-[var(--color-text)]">
        <section className="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-7 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--color-brand-solid)] text-xl font-black text-white">A</div>
          <h1 className="text-lg font-bold">Preparing your workspace</h1>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">Securely checking your account and business workspace.</p>
        </section>
      </main>
    );
  }

  const stats = computeStats(calendarItems, drafts, accounts.length, range);
  const series = buildSeries(calendarItems, range);
  const platforms = platformBreakdown(calendarItems, range);
  const searchQuery = workspaceSearch.trim().toLowerCase();
  const matchesSearch = (...values: Array<string | null | undefined>) => !searchQuery || values.some((value) => (value || "").toLowerCase().includes(searchQuery));
  const upcoming = calendarItems
    .filter((item) => item.kind !== "draft" && !isPublished(item) && !isFailed(item) && Boolean(item.scheduled_at) && new Date(item.scheduled_at as string).getTime() >= Date.now())
    .sort((x, y) => new Date(x.scheduled_at as string).getTime() - new Date(y.scheduled_at as string).getTime())
    .filter((item) => matchesSearch(item.title, item.content, item.platform, item.status));
  const firstName = namedUser?.full_name?.split(/\s+/)[0] || "there";

  return (
    <main className="bp-shell db-shell">
      <aside className="bp-sidebar">
        <Link href="/" className="bp-brand" aria-label="AutoBizPro home">
          <span className="bp-brand-mark">A</span>
          <span><span className="bp-brand-name">AutoBiz<span>Pro</span></span><span className="bp-brand-tag">Automate · Grow · Succeed</span></span>
        </Link>
        <nav aria-label="Main navigation" className="bp-nav">
          {navigation.map((item) => <Link key={item.href} href={item.href} aria-current={item.href === "/" ? "page" : undefined}><span className="bp-nav-icon" aria-hidden="true"><NavIcon name={item.icon} /></span>{item.label}</Link>)}
        </nav>
        <section className="bp-upgrade"><div className="bp-upgrade-icon">▣</div><strong className="text-sm">Business profile</strong><p>Keep your business details and brand information up to date.</p><Link href="/profile">Manage profile</Link></section>
      </aside>

      <div className="bp-main">
        <header className="bp-topbar">
          <div className="bp-topbar-leading">
            <h1 className="bp-topbar-title">Dashboard</h1>
            <label className="bp-search"><svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5" /></svg><input aria-label="Search drafts and connected accounts" value={workspaceSearch} onChange={(event) => setWorkspaceSearch(event.target.value)} placeholder="Search drafts and accounts…" /><button type="button" className="bp-search-clear" onClick={() => setWorkspaceSearch("")} aria-label="Clear search" hidden={!workspaceSearch}>×</button></label>
          </div>
          <div className="bp-top-actions">
            <button type="button" className="bp-icon-button" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} aria-pressed={theme === "dark"} onClick={toggleTheme} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}><Icon name={theme === "dark" ? "sun" : "moon"} size={18} /></button>
            <Link href="/activity" className="bp-icon-button bp-notification-link" aria-label="Open activity log" title="Recent activity"><svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg></Link>
            <Link href="/content" className="bp-top-create" aria-label="Create content"><span aria-hidden="true">＋</span><span className="bp-top-create-label">Create</span></Link>
            <div className="bp-user">
              <div className="bp-user-copy"><div className="bp-user-name">{namedUser?.full_name || "Your account"}</div><div className="bp-user-role">{organization?.role || "Workspace member"}</div></div>
              <div className="bp-profile-menu" ref={profileMenuRef}>
                <button type="button" className="bp-profile-trigger" aria-label={`Open profile and workspace menu for ${namedUser?.full_name || "your account"}`} aria-haspopup="true" aria-expanded={switcherOpen} aria-controls="dashboard-profile-menu" onClick={() => setSwitcherOpen((open) => !open)}>
                  <span className="bp-avatar">{initials}</span>
                  <svg aria-hidden="true" viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m5 7.5 5 5 5-5" /></svg>
                </button>
                {switcherOpen ? <div className="bp-profile-dropdown" id="dashboard-profile-menu" aria-label="Profile and workspace options">
                  <div className="bp-profile-summary"><span className="bp-profile-summary-avatar">{initials}</span><span><strong>{namedUser?.full_name || "Your account"}</strong><small>{currentUser?.email || organization?.name || "Demo workspace"}</small></span></div>
                  <Link href="/profile" onClick={() => setSwitcherOpen(false)}>Business profile</Link>
                  <Link href="/workspace" onClick={() => setSwitcherOpen(false)}>Workspace settings</Link>
                  <Link href="/security" onClick={() => setSwitcherOpen(false)}>Account security</Link>
                  <div className="bp-profile-divider" />
                  <p className="bp-profile-section-label">Switch workspace</p>
                  <div className="bp-profile-workspaces">{organizations.map((item) => <button type="button" aria-pressed={item.id === organization?.id} key={item.id} onClick={() => chooseOrganization(item)}><span className="bp-profile-workspace-name">{item.name}</span><small>{item.role}</small>{item.id === organization?.id ? <span className="bp-profile-current" aria-label="Current workspace">✓</span> : null}</button>)}</div>
                  <div className="bp-profile-divider" />
                  {creating ? <form onSubmit={handleCreateWorkspace} className="bp-profile-create-form"><label htmlFor="new-workspace">Workspace name</label><input id="new-workspace" required minLength={2} maxLength={160} value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Your business" />{createError ? <p role="alert">{createError}</p> : null}<div><button type="submit" disabled={createBusy}>{createBusy ? "Creating…" : "Create workspace"}</button><button type="button" onClick={() => { setCreating(false); setCreateError(""); }}>Cancel</button></div></form> : <button type="button" className="bp-profile-menu-action" onClick={() => setCreating(true)}>＋ Create workspace</button>}
                  <div className="bp-profile-divider" />
                  <button type="button" className="bp-profile-signout" onClick={() => { setSwitcherOpen(false); void signOut(); }}>Sign out</button>
                </div> : null}
              </div>
            </div>
          </div>
        </header>

        <div className="bp-content db-content">
          <div className="mb-3 empty:hidden"><ProfileCompletionPrompt organization={organization} user={currentUser} showModal /></div>

          <section className="db-welcome" aria-labelledby="dashboard-welcome">
            <div>
              <h1 id="dashboard-welcome">Welcome back, {firstName}! <span aria-hidden="true">👋</span></h1>
              <p>Here’s how {organization?.name ? `${organization.name}’s` : "your"} social media is performing today.</p>
            </div>
            <label className="db-range"><Icon name="clock" size={16} /><span className="sr-only">Reporting period</span>
              <Select value={range} onChange={(event) => setRange(Number(event.target.value) as RangeDays)}>{RANGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Select>
            </label>
          </section>

          {dataError ? <div role="alert" className="db-error">{dataError}<button type="button" onClick={() => { if (organization) setOrganization({ ...organization }); }}>Try again</button></div> : null}
          {!dataLoading && stats.failed > 0 ? <Link href="/calendar" className="db-alert"><Icon name="alert" size={18} /><span><b>{stats.failed} {stats.failed === 1 ? "post needs" : "posts need"} attention.</b> Review failed publications</span><Icon name="arrow" size={15} /></Link> : null}

          <LeadsDiscoveryCard />

          <section className="db-kpis" aria-label="Key metrics">
            <KpiCard href="/calendar" icon="send" tone="brand" label="Published posts" value={stats.published.current} trend={describeTrend(stats.published.current, stats.published.previous)} loading={dataLoading} />
            <KpiCard href="/calendar" icon="clock" tone="blue" label="Scheduled posts" value={stats.scheduled.current} trend={describeTrend(stats.scheduled.current, stats.scheduled.previous)} loading={dataLoading} />
            <KpiCard href="/content" icon="edit" tone="orange" label="New drafts" value={stats.drafts.current} trend={describeTrend(stats.drafts.current, stats.drafts.previous)} loading={dataLoading} />
            <KpiCard href="/social-accounts" icon="link" tone="green" label="Connected accounts" value={stats.accounts.total} hint={stats.accounts.total ? "Channels linked" : "None connected yet"} loading={dataLoading} />
          </section>

          <section className="db-grid-main">
            <Panel title="Performance overview" icon="chart" action={{ href: "/calendar", label: "View details" }} className="db-chart-panel">
              <PerformanceChart series={series} loading={dataLoading} />
            </Panel>
            <Panel title="Recent activity" icon="history" action={{ href: "/activity", label: "View all" }}>
              <ActivityList entries={activity} loading={dataLoading && !activity.length} />
            </Panel>
          </section>

          <section className="db-grid-secondary">
            <Panel title="Top platforms" icon="star" action={{ href: "/social-accounts", label: "View all" }}>
              <PlatformList rows={platforms} loading={dataLoading} />
            </Panel>
            <Panel title="Upcoming publications" icon="clock" action={{ href: "/calendar", label: "View calendar" }}>
              {dataLoading ? <EmptyState message="Loading your publishing queue…" /> : upcoming.length ? (
                <ul className="db-upcoming">{upcoming.slice(0, 4).map((item) => (
                  <li key={`${item.kind}-${item.id}`}>
                    <span className="db-date"><b>{new Date(item.scheduled_at as string).toLocaleDateString([], { day: "2-digit" })}</b><small>{new Date(item.scheduled_at as string).toLocaleDateString([], { month: "short" })}</small></span>
                    <span className="db-up-copy"><b>{item.title || "Untitled publication"}</b><small>{platformMeta(item.platform).label} · {new Date(item.scheduled_at as string).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</small></span>
                    <span className="db-chip">{item.status.replace(/[-_]/g, " ")}</span>
                  </li>))}</ul>
              ) : <EmptyState message={searchQuery ? "No publications match your search." : "Your publishing queue is clear."} href="/schedule-post" cta="Schedule a post" />}
            </Panel>
            <Panel title="Plan usage" icon="bolt" action={{ href: "/billing", label: "Upgrade plan" }}>
              <PlanUsage usage={usage} loading={dataLoading && !usage && !usageFailed} failed={usageFailed} />
            </Panel>
          </section>

          <section className="db-quick" aria-label="Quick actions">
            <Link href="/content" className="db-btn db-btn-primary"><Icon name="plus" size={16} /> Create new post</Link>
            <Link href="/social-accounts" className="db-btn">{accounts.length ? "Manage accounts" : "Connect social accounts"}</Link>
            {accounts.slice(0, 4).map((account) => <span key={account.id} className="db-account-pill"><PlatformBadge platform={account.provider} />{account.account_name || platformMeta(account.provider).label}</span>)}
          </section>

          <footer className="db-footer"><span>© 2026 AutoBizPro. All rights reserved.</span><span>Built to help your business grow.</span></footer>
        </div>
        <nav ref={mobileNavRef} aria-label="Mobile navigation" className="bp-mobile-nav min-[901px]:hidden">
          {[["Home", "/", "home"], ["Social", "/social-accounts", "share"], ["Leads", "/leads", "users"], ["Calendar", "/calendar", "calendar"]].map(([label, href, icon]) => <Link key={href} href={href} aria-current={(href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`) || (href === "/content" && pathname === "/schedule-post")) ? "page" : undefined}><span className="bp-mobile-nav-icon"><NavIcon name={icon} /></span><small>{label}</small></Link>)}
          <button type="button" className="bp-mobile-more" aria-label="More navigation options" aria-expanded={mobileMoreOpen} aria-current={navigation.filter((item) => !["/", "/social-accounts", "/leads", "/calendar"].includes(item.href)).some((item) => pathname === item.href || pathname.startsWith(`${item.href}/`)) ? "page" : undefined} aria-controls="bp-mobile-more-menu" onClick={() => setMobileMoreOpen((open) => !open)}><span className="bp-mobile-nav-icon"><NavIcon name="more" /></span><small>More</small></button>
          {mobileMoreOpen && <div className="bp-mobile-more-menu" id="bp-mobile-more-menu">{navigation.filter((item) => !["/", "/social-accounts", "/leads", "/calendar"].includes(item.href)).map((item) => <Link key={item.href} href={item.href} onClick={() => setMobileMoreOpen(false)} aria-current={(pathname === item.href || pathname.startsWith(`${item.href}/`) || (item.href === "/content" && pathname === "/schedule-post")) ? "page" : undefined}><span><NavIcon name={item.icon} /></span>{item.label}</Link>)}</div>}
        </nav>
      </div>
    </main>
  );
}
