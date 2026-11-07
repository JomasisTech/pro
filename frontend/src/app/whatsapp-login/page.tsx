"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { AuthShell, ErrorNote, SuccessNote, inputClass, primaryButtonClass } from "@/components/auth-shell";
import { fetchAuthProviders, requestWhatsAppCode, saveAuthSession, verifyWhatsAppCode } from "@/lib/auth";

type Step = "phone" | "code";

export default function WhatsAppLoginPage() {
  const [step, setStep] = useState<Step>("phone");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    void fetchAuthProviders().then((providers) => {
      if (!cancelled) setAvailable(providers.whatsapp);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function sendCode(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const message = await requestWhatsAppCode(phone.trim());
      setNotice(message);
      setStep("code");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We couldn't send the code. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function checkCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await verifyWhatsAppCode(phone.trim(), code.trim(), name.trim() || undefined);
      saveAuthSession(result);
      window.location.assign("/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in failed. Please try again.");
      setBusy(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Sign in with WhatsApp"
      title={step === "phone" ? "Use your WhatsApp number" : "Enter your code"}
      intro={
        step === "phone"
          ? "We'll send a 6-digit code to your WhatsApp. If you're new, your account is created automatically."
          : `We sent a 6-digit code to ${phone.trim()} on WhatsApp. It expires in 10 minutes.`
      }
    >
      {available === false ? (
        <div className="space-y-5">
          <ErrorNote>WhatsApp sign-in isn&apos;t available right now. Please use another way to sign in.</ErrorNote>
          <Link href="/login" className="block text-center text-sm font-bold text-[var(--auth-accent)] hover:underline">Back to sign in</Link>
        </div>
      ) : step === "phone" ? (
        <form onSubmit={sendCode} className="space-y-5">
          <div>
            <label htmlFor="phone" className="mb-2 block text-sm font-semibold">WhatsApp number</label>
            <input id="phone" type="tel" inputMode="tel" autoComplete="tel" required value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="+234 801 234 5678" className={inputClass} />
            <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">Include the country code, starting with +.</p>
          </div>
          {error ? <ErrorNote>{error}</ErrorNote> : null}
          <button type="submit" disabled={busy || available === null} className={primaryButtonClass}>{busy ? "Sending code…" : "Send code on WhatsApp"}</button>
          <Link href="/login" className="block text-center text-sm font-bold text-[var(--auth-accent)] hover:underline">Back to sign in</Link>
        </form>
      ) : (
        <form onSubmit={checkCode} className="space-y-5">
          {notice ? <SuccessNote>{notice}</SuccessNote> : null}
          <div>
            <label htmlFor="code" className="mb-2 block text-sm font-semibold">6-digit code</label>
            <input id="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} placeholder="123456" className={`${inputClass} tracking-[0.4em]`} />
          </div>
          <div>
            <label htmlFor="name" className="mb-2 block text-sm font-semibold">Your name <span className="font-normal text-[var(--color-text-muted)]">(optional, for new accounts)</span></label>
            <input id="name" autoComplete="name" maxLength={160} value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Alex Morgan" className={inputClass} />
          </div>
          {error ? <ErrorNote>{error}</ErrorNote> : null}
          <button type="submit" disabled={busy || code.length !== 6} className={primaryButtonClass}>{busy ? "Checking…" : "Verify and continue"}</button>
          <div className="flex items-center justify-between gap-3 text-sm">
            <button type="button" disabled={busy} onClick={() => void sendCode()} className="font-bold text-[var(--auth-accent)] hover:underline disabled:opacity-60">Send a new code</button>
            <button type="button" onClick={() => { setStep("phone"); setCode(""); setError(""); setNotice(""); }} className="font-bold text-[var(--color-text-muted)] hover:underline">Change number</button>
          </div>
        </form>
      )}
    </AuthShell>
  );
}
