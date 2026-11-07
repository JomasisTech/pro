"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export default function SocialOAuthCallbackPage() {
  const [result, setResult] = useState<string | null>(null);
  useEffect(() => { setResult(new URLSearchParams(window.location.search).get("result")); }, []);
  const success = result === "connected";
  const cancelled = result === "cancelled";
  const provider = typeof window === "undefined" ? "social platform" : (new URLSearchParams(window.location.search).get("provider") || "social platform");
  const providerName = provider === "tiktok" ? "TikTok" : provider === "instagram" ? "Instagram" : provider === "facebook" ? "Facebook Pages" : provider;
  return <main className="flex min-h-screen items-center justify-center bg-[var(--color-page)] px-4 text-[var(--color-text)]"><section className="w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-7 text-center"><h1 className="text-2xl font-extrabold">{success ? `${providerName} connected` : cancelled ? `${providerName} connection cancelled` : result === null ? "Checking connection…" : `${providerName} connection not completed`}</h1><p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">{success ? `${providerName} confirmed authorization and AutoBizPro saved the account connection.` : cancelled ? `You cancelled ${providerName} authorization. No account was connected.` : result === null ? "Please wait while we read the authorization result." : `AutoBizPro could not complete ${providerName} authorization. Check the platform setup and try again.`}</p><Link href="/social-accounts" className="mt-6 inline-flex rounded-xl bg-[var(--color-brand)] px-5 py-3 text-sm font-bold text-white">Return to social accounts</Link></section></main>;
}
