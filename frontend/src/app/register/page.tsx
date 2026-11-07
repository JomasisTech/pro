"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { clearAuthSession, getApiBaseUrl, registerAccount } from "@/lib/auth";
import { SocialSignInButtons } from "@/components/social-auth";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Use a password with at least 8 characters.");
      return;
    }

    setBusy(true);
    try {
      const result = await registerAccount({
        full_name: fullName.trim(),
        organization_name: organizationName.trim(),
        email: email.trim(),
        password,
      });
      // Registration sends a verification email. Do not keep the provisional bearer token in the browser.
      clearAuthSession();
      window.location.assign("/verify-email");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Registration failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page auth-page-centered min-h-screen px-4 py-8 text-white sm:px-6">
      <div className="auth-centered-shell mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-xl flex-col items-center justify-center">
        <div className="mb-7"><Brand inverted /></div>
        <section className="auth-card auth-form-panel w-full rounded-[2rem] p-6 sm:p-10">
          <div className="mx-auto w-full max-w-md">
            <div className="mb-7 text-center">
              <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-[2.15rem]">Create your account</h1>
              <p className="mt-2 text-sm leading-6 text-[var(--auth-form-muted)]">Set up your workspace and get started with AutoBizPro.</p>
            </div>
            <SocialSignInButtons action="Sign up" />
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="fullName" className="mb-2 block text-sm font-semibold text-white/95">Your full name</label>
                <input id="fullName" autoComplete="name" required minLength={1} maxLength={160} value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="e.g. Alex Morgan" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3 text-base text-white outline-none transition placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              <div>
                <label htmlFor="organizationName" className="mb-2 block text-sm font-semibold text-white/95">Business or organization name</label>
                <input id="organizationName" autoComplete="organization" required minLength={2} maxLength={160} value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} placeholder="e.g. Morgan Creative Studio" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3 text-base text-white outline-none transition placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              <div>
                <label htmlFor="email" className="mb-2 block text-sm font-semibold text-white/95">Email address</label>
                <input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3 text-base text-white outline-none transition placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              <div>
                <label htmlFor="password" className="mb-2 block text-sm font-semibold text-white/95">Password</label>
                <input id="password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3 text-base text-white outline-none transition placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              <div>
                <label htmlFor="confirmPassword" className="mb-2 block text-sm font-semibold text-white/95">Confirm password</label>
                <input id="confirmPassword" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Enter the same password again" className="auth-input w-full rounded-xl border border-[var(--auth-form-border)] bg-white/[0.06] px-4 py-3 text-base text-white outline-none transition placeholder:text-white/45 focus:border-violet-300 focus:ring-2 focus:ring-violet-300/20" />
              </div>
              {error ? <div role="alert" className="rounded-xl border border-rose-300/40 bg-rose-950/35 px-4 py-3 text-sm leading-5 text-rose-100">{error}</div> : null}
              <button type="submit" disabled={busy} className="auth-submit w-full rounded-xl px-4 py-3.5 text-sm font-bold text-[#1c1030] shadow-sm transition disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Creating account…" : "Create account"}</button>
            </form>
            <p className="mt-6 text-center text-sm text-[var(--auth-form-muted)]">Already have an account? <Link href="/login" className="font-bold text-violet-200 hover:text-white hover:underline">Sign in</Link></p>
            {process.env.NODE_ENV !== "production" ? <p className="mt-7 break-words text-center text-[11px] leading-5 text-white/45">API endpoint: {getApiBaseUrl()}</p> : null}
          </div>
        </section>
        <p className="mt-6 text-center text-[11px] tracking-wide text-white/55">A clearer way to manage your business</p>
      </div>
    </main>
  );
}

function Brand({ inverted = false }: { inverted?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex h-11 w-11 items-center justify-center rounded-2xl text-xl font-black ${inverted ? "bg-white text-[var(--auth-accent)]" : "bg-[var(--color-brand-solid)] text-white"}`}>A</div>
      <div>
        <p className="text-xl font-extrabold tracking-tight">AutoBiz<span className={inverted ? "text-white/80" : "text-[var(--auth-accent)]"}>Pro</span></p>
        <p className={`text-[10px] ${inverted ? "text-white/70" : "text-[var(--color-text-muted)]"}`}>Automate · Grow · Succeed</p>
      </div>
    </div>
  );
}
