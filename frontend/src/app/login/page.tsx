"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { fetchDemoInfo, getApiBaseUrl, loginAccount, saveAuthSession, type DemoInfo } from "@/lib/auth";
import { SocialSignInButtons, socialErrorMessage } from "@/components/social-auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [socialError, setSocialError] = useState("");
  const [demo, setDemo] = useState<DemoInfo>({ enabled: false });

  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("social_error");
    if (code) setSocialError(socialErrorMessage(code));
    void fetchDemoInfo().then(setDemo);
  }, []);

  async function signIn(credentials: { email: string; password: string; totp_code?: string }) {
    setError("");
    setBusy(true);
    try {
      const result = await loginAccount(credentials);
      saveAuthSession(result);
      const next = new URLSearchParams(window.location.search).get("next");
      let destination = "/";
      if (next?.startsWith("/") && !next.startsWith("//")) {
        try {
          const target = new URL(next, window.location.origin);
          if (target.origin === window.location.origin) {
            destination = `${target.pathname}${target.search}${target.hash}`;
          }
        } catch {
          destination = "/";
        }
      }
      window.location.assign(destination);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Login failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void signIn({ email: email.trim(), password, ...(totpCode.trim() ? { totp_code: totpCode.trim() } : {}) });
  }

  return (
    <main className="auth-page auth-page-centered min-h-screen px-4 py-8 text-white sm:px-6">
      <div className="auth-centered-shell mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-xl flex-col items-center justify-center">
        <div className="mb-7"><Brand inverted /></div>
        <section className="auth-card auth-form-panel w-full rounded-[2rem] p-6 sm:p-10">
          <div className="mx-auto w-full max-w-md">
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-[2.15rem]">Welcome back</h1>
              <p className="mt-2 text-sm text-[var(--auth-form-muted)]">Sign in to your account</p>
            </div>

            {demo.enabled ? (
              <div className="mb-5 rounded-2xl border border-white/20 bg-white/[0.07] px-4 py-3 text-sm leading-6">
                <p className="font-bold text-white">Demo mode</p>
                <p className="text-[var(--auth-form-muted)]">Email: {demo.email} · Password: {demo.password}</p>
                <button type="button" disabled={busy} onClick={() => { setEmail(demo.email); setPassword(demo.password); void signIn({ email: demo.email, password: demo.password }); }} className="mt-3 w-full rounded-xl border border-violet-300/50 px-4 py-2.5 text-sm font-bold text-violet-100 transition hover:bg-white/10 disabled:opacity-60">Enter customer demo</button>
              </div>
            ) : null}
            {socialError ? <div role="alert" className="mb-5 rounded-xl border border-rose-300/40 bg-rose-950/35 px-4 py-3 text-sm text-rose-100">{socialError}</div> : null}
            <SocialSignInButtons />
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="email" className="mb-2 block text-sm font-semibold text-white/95">Email address</label>
                <input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3.5 text-base text-white outline-none transition placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between gap-3"><label htmlFor="password" className="block text-sm font-semibold text-white/95">Password</label><Link href="/forgot-password" className="text-xs font-semibold text-violet-200 hover:text-white hover:underline">Forgot password?</Link></div>
                <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3.5 text-base text-white outline-none transition placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              <div>
                <label htmlFor="totp-code" className="mb-2 block text-sm font-semibold text-white/95">Authenticator code <span className="font-normal text-white/55">(platform administrators)</span></label>
                <input id="totp-code" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" maxLength={8} value={totpCode} onChange={(event) => setTotpCode(event.target.value.replace(/\D/g, "").slice(0, 8))} placeholder="Enter your 6-digit code" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3.5 text-base tracking-[0.25em] text-white outline-none transition placeholder:tracking-normal placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              {error ? <div role="alert" className="rounded-xl border border-rose-300/40 bg-rose-950/35 px-4 py-3 text-sm leading-5 text-rose-100">{error}</div> : null}
              <button type="submit" disabled={busy} className="auth-submit w-full rounded-xl px-4 py-3.5 text-sm font-bold text-[#1c1030] shadow-sm transition disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Signing in…" : "Sign in"}</button>
            </form>
            <p className="mt-7 text-center text-sm text-[var(--auth-form-muted)]">New here? <Link href="/register" className="font-bold text-violet-200 hover:text-white hover:underline">Create an account</Link></p>
            {process.env.NODE_ENV !== "production" ? <p className="mt-7 break-words text-center text-[11px] leading-5 text-white/45">API endpoint: {getApiBaseUrl()}</p> : null}
          </div>
        </section>
        <p className="mt-6 text-center text-[11px] tracking-wide text-white/55">Secure access to your AutoBizPro workspace</p>
      </div>
    </main>
  );
}

function Brand({ inverted = false }: { inverted?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex h-11 w-11 items-center justify-center rounded-2xl text-xl font-black ${inverted ? "bg-white text-[#5b21b6]" : "bg-[var(--color-brand-solid)] text-white"}`}>A</div>
      <div>
        <p className={`text-xl font-extrabold tracking-tight ${inverted ? "text-white" : "text-[var(--color-text)]"}`}>AutoBiz<span className={inverted ? "text-violet-200" : "text-[var(--auth-accent)]"}>Pro</span></p>
        <p className={`text-[10px] ${inverted ? "text-white/70" : "text-[var(--auth-form-muted)]"}`}>Automate · Grow · Succeed</p>
      </div>
    </div>
  );
}
