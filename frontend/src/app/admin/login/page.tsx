"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { loginAccount, loginDemoPlatformAdmin, saveAuthSession, type DemoInfo, fetchDemoInfo } from "@/lib/auth";

export default function AdminLoginPage() {
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void fetchDemoInfo().then((info: DemoInfo) => setDemoEnabled(info.enabled));
  }, []);

  async function finishSignIn(action: () => Promise<Awaited<ReturnType<typeof loginAccount>>>) {
    setBusy(true);
    setError("");
    try {
      const session = await action();
      saveAuthSession(session);
      window.location.assign("/platform");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in to the administrator dashboard.");
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void finishSignIn(() => loginAccount({
      email: email.trim(), password,
      ...(totpCode.trim() ? { totp_code: totpCode.trim() } : {}),
    }));
  }

  return <main className="flex min-h-screen items-center justify-center bg-[var(--page)] px-5 py-12">
    <section className="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-7 shadow-xl">
      <p className="text-xs font-bold uppercase tracking-[.16em] text-[var(--color-brand)]">Restricted access</p>
      <h1 className="mt-3 text-2xl font-extrabold">Administrator sign in</h1>
      <p className="mt-3 text-sm text-[var(--text-muted)]">Sign in to the AutoBizPro platform-owner dashboard. Configured production owners and delegated administrators must use their password and authenticator code.</p>
      {demoEnabled ? <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
        <p className="text-sm font-bold">Platform administrator demo</p>
        <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">Enter the isolated demo dashboard with sample platform data. No account creation, authenticator setup or production credentials are needed.</p>
        <button type="button" disabled={busy} onClick={() => void finishSignIn(loginDemoPlatformAdmin)} className="mt-4 w-full rounded-xl bg-[var(--color-brand)] px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Opening demo…" : "Enter administrator demo"}</button>
      </div> : null}
      <div className="mt-6">
        <p className="text-sm font-bold">Administrator credentials</p>
        <form onSubmit={handleSubmit} className="mt-3 space-y-3">
          <label className="block text-xs font-semibold">Email address
            <input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="owner@yourcompany.com" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] px-3 py-2.5 text-sm" />
          </label>
          <label className="block text-xs font-semibold">Password
            <input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Your password" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] px-3 py-2.5 text-sm" />
          </label>
          <label className="block text-xs font-semibold">Authenticator code
            <input type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" maxLength={8} value={totpCode} onChange={(event) => setTotpCode(event.target.value.replace(/\D/g, "").slice(0, 8))} placeholder="6-digit code" className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--page)] px-3 py-2.5 text-sm tracking-[.2em]" />
          </label>
          {error ? <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-600">{error}</p> : null}
          <button type="submit" disabled={busy} className="w-full rounded-xl border border-[var(--color-border)] px-4 py-3 text-sm font-bold disabled:opacity-60">{busy ? "Signing in…" : "Sign in as administrator"}</button>
        </form>
      </div>
      <Link href="/login" className="mt-6 block text-center text-sm font-semibold text-[var(--color-brand)]">Go to customer sign in</Link>
      <p className="mt-4 text-xs leading-5 text-[var(--text-muted)]">Demo administrator access exists only when the backend has DEMO_MODE=true. The demo shortcut does not disable MFA for real administrator accounts.</p>
    </section>
  </main>;
}
