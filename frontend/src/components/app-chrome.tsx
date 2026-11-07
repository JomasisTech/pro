"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { getAccessToken } from "@/lib/auth";

const items = [
  ["Home", "/", "home"], ["Social accounts", "/social-accounts", "share"], ["Brand Intelligence", "/brand-intelligence", "sparkle"], ["Leads", "/leads", "users"],
  ["Content calendar", "/calendar", "calendar"], ["Content studio", "/content", "edit"],
  ["TikTok publishing", "/tiktok-publish", "video"], ["Facebook publishing", "/facebook-publish", "facebook"],
  ["YouTube publishing", "/youtube-publish", "play"], ["Business profile", "/profile", "building"],
  ["Products & services", "/products", "package"], ["Activity log", "/activity", "activity"],
  ["Workspace settings", "/workspace", "settings"], ["Billing", "/billing", "credit-card"], ["Account security", "/security", "lock"],
];

const iconPaths: Record<string, string> = {
  home: "M3 10.8 12 3l9 7.8V21h-6v-6H9v6H3z",
  share: "M18 8a3 3 0 1 0-2.8-3M6 12l9-4M6 12l9 4M9 12a3 3 0 1 0-6 0 3 3 0 0 0 6 0M21 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  sparkle: "m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
  calendar: "M4 5h16v16H4zM8 3v4M16 3v4M4 10h16M8 14h2M14 14h2M8 18h2",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M20 8v6M23 11h-6",
  shield: "M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11zM9 12l2 2 4-4",
  "check-circle": "M22 11.1V12a10 10 0 1 1-5.9-9.1M22 4 12 14.01l-3-3",
  bookmark: "M6 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-6-4-6 4z",
  target: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
  edit: "M4 20h4l11-11a2.1 2.1 0 0 0-4-4L4 16zM13.5 6.5l4 4",
  video: "M4 6h11a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zM17 10l5-3v10l-5-3",
  facebook: "M14 8h3V4h-3a5 5 0 0 0-5 5v3H6v4h3v5h4v-5h3l1-4h-4V9a1 1 0 0 1 1-1z",
  play: "M5 3v18l15-9z",
  building: "M3 21h18M5 21V5l7-2v18M12 8h7v13M8 7h1M8 11h1M8 15h1M15 11h1M15 15h1",
  package: "m12 3 9 5v9l-9 5-9-5V8zM3 8l9 5 9-5M12 13v9M8 5l9 5",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 3.1-.2-.1a1.7 1.7 0 0 0-1.8.1l-.2.1h-3.6l-.1-.2a1.7 1.7 0 0 0-1.6-1l-.2.1-3.1-1.8.1-.2a1.7 1.7 0 0 0-.1-1.8l-.1-.2v-3.6l.2-.1a1.7 1.7 0 0 0 1-1.6l-.1-.2 1.8-3.1.2.1a1.7 1.7 0 0 0 1.8-.1l.2-.1h3.6l.1.2a1.7 1.7 0 0 0 1.6 1l.2-.1 3.1 1.8-.1.2a1.7 1.7 0 0 0 .1 1.8l.1.2v3.6z",
  "credit-card": "M3 6h18v13H3zM3 10h18M7 15h4",
  lock: "M5 10h14v11H5zM8 10V7a4 4 0 1 1 8 0v3",
  more: "M5 12h.01M12 12h.01M19 12h.01",
};

export function NavIcon({ name }: { name: string }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={iconPaths[name] ?? iconPaths.more} /></svg>;
}

function ThemeIcon({ dark }: { dark: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={dark ? "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z" : "M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2z"} /></svg>;
}

export default function AppChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  const mobileNavRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const saved = localStorage.getItem("bizpilotpro-theme") ?? localStorage.getItem("autobizpro-theme");
    const next = saved === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    setTheme(next);
  }, []);
  useEffect(() => { setMobileMoreOpen(false); }, [pathname]);
  useEffect(() => {
    if (!mobileMoreOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileMoreOpen(false); };
    const closeOutside = (event: PointerEvent) => { if (!mobileNavRef.current?.contains(event.target as Node)) setMobileMoreOpen(false); };
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOutside);
    return () => { document.removeEventListener("keydown", closeOnEscape); document.removeEventListener("pointerdown", closeOutside); };
  }, [mobileMoreOpen]);
  useEffect(() => {
    const token = getAccessToken();
    if (!token) { setIsPlatformAdmin(false); return; }
    const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
    let cancelled = false;
    void fetch(`${apiBase}/api/v1/billing/admin/prices`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" })
      .then((response) => { if (!cancelled) setIsPlatformAdmin(response.ok); })
      .catch(() => { if (!cancelled) setIsPlatformAdmin(false); });
    return () => { cancelled = true; };
  }, [pathname]);
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("bizpilotpro-theme", next);
    setTheme(next);
  };
  if (["/", "/login", "/register", "/whatsapp-login", "/verify-email", "/auth/callback", "/forgot-password", "/reset-password", "/onboarding", "/social-accounts/callback"].includes(pathname)) return <>{children}</>;
  const adminItems = isPlatformAdmin ? [["Platform administration", "/platform", "settings"], ["Subscription pricing", "/platform/billing-prices", "credit-card"]] : [];
  const mobilePrimary = [items[0], items[1], items[3], items[4]];
  const isRouteActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`) || (href === "/content" && pathname === "/schedule-post");
  const moreItems = [...items.slice(2, 3), ...items.slice(5), ...adminItems];
  const moreIsActive = moreItems.some(([, href]) => isRouteActive(href));
  const currentPageLabel = [...items, ...adminItems].find(([, href]) => isRouteActive(href))?.[0] ?? (pathname === "/schedule-post" ? "Content studio" : "AutoBizPro");
  return <div className="app-chrome">
    <aside className="app-chrome-sidebar">
      <Link href="/" className="app-chrome-brand"><span className="app-chrome-mark">A</span><span>AutoBiz<strong>Pro</strong></span></Link>
      <nav aria-label="Application navigation">{items.map(([label, href, icon]) => <Link key={href} href={href} aria-current={isRouteActive(href) ? "page" : undefined}><span className="app-chrome-nav-icon"><NavIcon name={icon} /></span>{label}</Link>)}{adminItems.map(([label, href, icon]) => <Link key={href} href={href} aria-current={isRouteActive(href) ? "page" : undefined}><span className="app-chrome-nav-icon"><NavIcon name={icon} /></span>{label}</Link>)}</nav>
      <Link className="app-chrome-profile" href="/profile">Business profile & settings →</Link>
    </aside>
    <div className="app-chrome-main">
      <header className="app-chrome-top"><span className="app-chrome-page">{currentPageLabel}</span><div><button type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}><ThemeIcon dark={theme === "dark"} /></button><Link href="/content" className="app-chrome-create">＋ Create content</Link></div></header>
      <div className="app-chrome-content">{children}</div>
    </div>
    <nav ref={mobileNavRef} className="app-chrome-mobile" aria-label="Mobile navigation">
      {mobilePrimary.map(([label, href, icon]) => <Link key={href} href={href} aria-current={isRouteActive(href) ? "page" : undefined}><span className="app-chrome-nav-icon"><NavIcon name={icon} /></span><small>{label === "Leads" ? "Leads" : label === "Social accounts" ? "Social" : label === "Content calendar" ? "Calendar" : label}</small></Link>)}
      <button type="button" className="app-chrome-more-trigger" aria-label="More navigation options" aria-current={moreIsActive ? "page" : undefined} aria-expanded={mobileMoreOpen} aria-controls="app-mobile-more" onClick={() => setMobileMoreOpen((open) => !open)}><span className="app-chrome-nav-icon"><NavIcon name="more" /></span><small>More</small></button>
      {mobileMoreOpen && <div className="app-chrome-more-menu" id="app-mobile-more">{moreItems.map(([label, href, icon]) => <Link key={href} href={href} onClick={() => setMobileMoreOpen(false)} aria-current={isRouteActive(href) ? "page" : undefined}><span className="app-chrome-nav-icon"><NavIcon name={icon} /></span>{label}</Link>)}</div>}
    </nav>
  </div>;
}
