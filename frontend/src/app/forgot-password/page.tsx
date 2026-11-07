"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AuthShell, ErrorNote, SuccessNote, inputClass, primaryButtonClass } from "@/components/auth-shell";
import { requestPasswordReset } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      setSent(await requestPasswordReset(email.trim()));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't send the reset email. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell eyebrow="Account recovery" title="Reset your password" intro="Enter the email address you signed up with. If an account exists, we'll email you a link to choose a new password.">
      {sent ? (
        <div className="space-y-5">
          <SuccessNote>{sent} The link expires in 30 minutes. Check your spam folder if you don&apos;t see it.</SuccessNote>
          <Link href="/login" className="block text-center text-sm font-bold text-[var(--color-brand)] hover:underline">Back to sign in</Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="mb-2 block text-sm font-semibold">Email address</label>
            <input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" className={inputClass} />
          </div>
          {error ? <ErrorNote>{error}</ErrorNote> : null}
          <button type="submit" disabled={busy} className={primaryButtonClass}>{busy ? "Sending…" : "Send reset link"}</button>
          <Link href="/login" className="block text-center text-sm font-bold text-[var(--color-brand)] hover:underline">Back to sign in</Link>
        </form>
      )}
    </AuthShell>
  );
}
