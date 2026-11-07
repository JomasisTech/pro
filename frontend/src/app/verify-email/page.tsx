"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { AuthShell, ErrorNote, SuccessNote, inputClass, primaryButtonClass } from "@/components/auth-shell";
import { resendVerification, verifyEmail } from "@/lib/auth";

export default function VerifyEmailPage() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token");
    setToken(value ?? "");
    if (value) window.history.replaceState(null, "", window.location.pathname);
    if (value) {
      setBusy(true);
      verifyEmail(value).then(setMessage).catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Verification failed. Request a new link.");
      }).finally(() => setBusy(false));
    }
  }, []);

  async function handleResend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try { setMessage(await resendVerification(email.trim())); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not request a new link."); }
    finally { setBusy(false); }
  }

  return (
    <AuthShell eyebrow="Account security" title="Verify your email" intro="Open the verification link we emailed you. If it has expired or is missing, request a fresh one below.">
      {busy ? <p className="text-sm text-[var(--color-text-muted)]">Checking your verification link…</p> : null}
      {message ? <div className="space-y-5"><SuccessNote>{message}</SuccessNote><Link href="/login" className={`${primaryButtonClass} block text-center`}>Go to sign in</Link></div> : null}
      {error ? <div className="space-y-4"><ErrorNote>{error}</ErrorNote><form onSubmit={handleResend} className="space-y-3"><label htmlFor="verification-email" className="block text-sm font-semibold">Account email</label><input id="verification-email" type="email" required autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} className={inputClass} placeholder="you@example.com"/><button disabled={busy} className={primaryButtonClass} type="submit">Send a new verification link</button></form></div> : null}
      {token === "" && !error ? <div className="space-y-4"><p className="text-sm text-[var(--color-text-muted)]">The verification link is missing its code. Enter your account email to request another.</p><form onSubmit={handleResend} className="space-y-3"><label htmlFor="verification-email" className="block text-sm font-semibold">Account email</label><input id="verification-email" type="email" required autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} className={inputClass} placeholder="you@example.com"/><button disabled={busy} className={primaryButtonClass} type="submit">Send verification link</button></form></div> : null}
    </AuthShell>
  );
}
