"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { AuthShell, ErrorNote, SuccessNote, inputClass, primaryButtonClass } from "@/components/auth-shell";
import { resetPassword } from "@/lib/auth";

export default function ResetPasswordPage() {
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  useEffect(() => {
    // The emailed link carries the secret in the URL fragment (#token=...), which browsers never send to
    // servers. Read it once, then remove it from the address bar and history.
    const found = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token");
    setToken(found ?? "");
    if (found) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password.length < 8) return setError("Use at least 8 characters.");
    if (password !== confirm) return setError("The two passwords don't match.");
    if (!token) return;
    setBusy(true);
    try {
      setDone(await resetPassword(token, password));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't reset the password. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (token === null) return <AuthShell eyebrow="Account recovery" title="Choose a new password" intro="Checking your link…"><span /></AuthShell>;

  return (
    <AuthShell eyebrow="Account recovery" title="Choose a new password" intro="Pick a strong, unique password. Signing in elsewhere will be required again after the change.">
      {done ? (
        <div className="space-y-5">
          <SuccessNote>{done}</SuccessNote>
          <Link href="/login" className={`${primaryButtonClass} block text-center`}>Go to sign in</Link>
        </div>
      ) : token === "" ? (
        <div className="space-y-5">
          <ErrorNote>This reset link is missing its code. Open the link from your email again, or request a new one.</ErrorNote>
          <Link href="/forgot-password" className="block text-center text-sm font-bold text-[var(--color-brand)] hover:underline">Request a new link</Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="new-password" className="mb-2 block text-sm font-semibold">New password</label>
            <input id="new-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="confirm-password" className="mb-2 block text-sm font-semibold">Confirm new password</label>
            <input id="confirm-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} className={inputClass} />
          </div>
          {error ? <ErrorNote>{error}</ErrorNote> : null}
          <button type="submit" disabled={busy} className={primaryButtonClass}>{busy ? "Saving…" : "Update password"}</button>
          {error.includes("expired") ? <Link href="/forgot-password" className="block text-center text-sm font-bold text-[var(--color-brand)] hover:underline">Request a new link</Link> : null}
        </form>
      )}
    </AuthShell>
  );
}
