"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorNote, SuccessNote, inputClass, primaryButtonClass } from "@/components/auth-shell";
import { changePassword, setAccountCredentials, clearAuthSession, fetchCurrentUser, getAccessToken, hasPlaceholderName, logoutEverywhere, saveAuthSession, updateAccountName } from "@/lib/auth";

export default function SecurityPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [everywhereBusy, setEverywhereBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [hasPassword, setHasPassword] = useState(true);
  const [fullName, setFullName] = useState("");
  const [nameBusy, setNameBusy] = useState(false);
  const [nameNotice, setNameNotice] = useState("");
  const [nameError, setNameError] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [setupConfirm, setSetupConfirm] = useState("");
  const [setupBusy, setSetupBusy] = useState(false);
  const [setupError, setSetupError] = useState("");
  const [setupNotice, setSetupNotice] = useState("");
  const [totpEnabled, setTotpEnabled] = useState(false);
  const [totpUri, setTotpUri] = useState("");
  const [totpSecret, setTotpSecret] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [totpBusy, setTotpBusy] = useState(false);
  const [totpError, setTotpError] = useState("");
  const [totpNotice, setTotpNotice] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setReady(true);
    fetchCurrentUser(token)
      .then(async (user) => {
        setEmail(user.email ?? "");
        setHasPassword(user.has_password);
        // WhatsApp accounts start with a placeholder name; leave the box empty so they type a real one.
        setFullName(hasPlaceholderName(user) ? "" : user.full_name);
        const statusResponse = await fetch(`${(process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "")}/api/v1/auth/2fa/status`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
        if (statusResponse.ok) setTotpEnabled((await statusResponse.json()).enabled === true);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  async function startTotpSetup() {
    const token = getAccessToken(); if (!token) return router.replace("/login");
    setTotpError(""); setTotpNotice(""); setTotpBusy(true);
    try {
      const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
      const response = await fetch(`${base}/api/v1/auth/2fa/setup`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not start authenticator setup.");
      setTotpUri(data.otpauth_uri); setTotpSecret(data.secret);
    } catch (e) { setTotpError(e instanceof Error ? e.message : "Could not start setup."); }
    finally { setTotpBusy(false); }
  }

  async function verifyTotpSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const token = getAccessToken(); if (!token) return router.replace("/login");
    setTotpError(""); setTotpNotice(""); setTotpBusy(true);
    try {
      const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
      const response = await fetch(`${base}/api/v1/auth/2fa/verify`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ code: totpCode }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Invalid authenticator code.");
      setTotpEnabled(true); setTotpUri(""); setTotpSecret(""); setTotpCode(""); setTotpNotice(data.message);
    } catch (e) { setTotpError(e instanceof Error ? e.message : "Could not verify code."); }
    finally { setTotpBusy(false); }
  }

  async function handleNameChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNameError("");
    setNameNotice("");
    const token = getAccessToken();
    if (!token) return router.replace("/login");
    setNameBusy(true);
    try {
      const user = await updateAccountName(token, fullName.trim());
      setFullName(user.full_name);
      setNameNotice("Name updated.");
    } catch (reason) {
      setNameError(reason instanceof Error ? reason.message : "Couldn't update your name. Please try again.");
    } finally {
      setNameBusy(false);
    }
  }

  async function handleSetCredentials(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSetupError("");
    setSetupNotice("");
    const token = getAccessToken();
    if (!token) return router.replace("/login");
    if (setupPassword.length < 8) return setSetupError("Use at least 8 characters for the password.");
    if (setupPassword !== setupConfirm) return setSetupError("The two passwords don't match.");
    setSetupBusy(true);
    try {
      const needsEmail = !email;
      // The server ends other sessions and returns a fresh token for this one.
      const result = await setAccountCredentials(token, setupPassword, needsEmail ? newEmail.trim() : undefined);
      saveAuthSession(result);
      setEmail(result.user.email ?? "");
      setHasPassword(result.user.has_password);
      setSetupPassword(""); setSetupConfirm(""); setNewEmail("");
      setSetupNotice(needsEmail ? "Saved. We sent a link to confirm your email address. Your other sessions were signed out." : "Password added. Your other sessions were signed out.");
    } catch (reason) {
      setSetupError(reason instanceof Error ? reason.message : "Couldn't save. Please try again.");
    } finally {
      setSetupBusy(false);
    }
  }

  async function handleChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const token = getAccessToken();
    if (!token) return router.replace("/login");
    if (next.length < 8) return setError("Use at least 8 characters for the new password.");
    if (next !== confirm) return setError("The two new passwords don't match.");
    setBusy(true);
    try {
      // The server ends all other sessions and returns a fresh token for this one.
      saveAuthSession(await changePassword(token, current, next));
      setCurrent(""); setNext(""); setConfirm("");
      setNotice("Password updated. Your other sessions were signed out.");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Couldn't change the password. Please try again.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSignOutEverywhere() {
    const token = getAccessToken();
    if (!token) return router.replace("/login");
    setError("");
    setEverywhereBusy(true);
    try {
      await logoutEverywhere(token);
      clearAuthSession();
      router.replace("/login");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't sign out of all devices. Please try again.");
      setEverywhereBusy(false);
    }
  }

  if (!ready) return null;

  return (
    <div className="mx-auto w-full max-w-xl space-y-8 px-4 py-6 sm:px-6">
      <section>
        <h1 className="text-2xl font-extrabold tracking-tight">Account security</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">Manage your account details and sign-in, or end every active session.</p>
      </section>

      <form onSubmit={handleNameChange} className="space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <h2 className="text-lg font-bold">Your account</h2>
        <div>
          <label htmlFor="account-email" className="mb-2 block text-sm font-semibold">Email address</label>
          <input id="account-email" type="email" value={email} placeholder="No email on this account" readOnly disabled className={`${inputClass} opacity-70`} />
          <p className="mt-2 text-xs text-[var(--color-text-muted)]">{email ? "Changing the email address isn't available yet." : "There is no email address on this account yet. You can add one below."}</p>
        </div>
        <div>
          <label htmlFor="account-name" className="mb-2 block text-sm font-semibold">Full name</label>
          <input id="account-name" required maxLength={160} placeholder="Your name" value={fullName} onChange={(event) => setFullName(event.target.value)} autoComplete="name" className={inputClass} />
        </div>
        {nameError ? <ErrorNote>{nameError}</ErrorNote> : null}
        {nameNotice ? <SuccessNote>{nameNotice}</SuccessNote> : null}
        <button type="submit" disabled={nameBusy || !fullName.trim()} className={primaryButtonClass}>{nameBusy ? "Saving…" : "Save name"}</button>
      </form>

      {hasPassword ? (
      <form onSubmit={handleChange} className="space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <h2 className="text-lg font-bold">Change password</h2>
        <div>
          <label htmlFor="current-password" className="mb-2 block text-sm font-semibold">Current password</label>
          <input id="current-password" type="password" autoComplete="current-password" required value={current} onChange={(event) => setCurrent(event.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="next-password" className="mb-2 block text-sm font-semibold">New password</label>
          <input id="next-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={next} onChange={(event) => setNext(event.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="confirm-new-password" className="mb-2 block text-sm font-semibold">Confirm new password</label>
          <input id="confirm-new-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} className={inputClass} />
        </div>
        {error ? <ErrorNote>{error}</ErrorNote> : null}
        {notice ? <SuccessNote>{notice}</SuccessNote> : null}
        <button type="submit" disabled={busy} className={primaryButtonClass}>{busy ? "Saving…" : "Update password"}</button>
      </form>
      ) : (
        <form onSubmit={handleSetCredentials} className="space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <div>
            <h2 className="text-lg font-bold">{email ? "Add a password" : "Add an email and password"}</h2>
            <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">{email ? "You currently sign in with Google or WhatsApp. A password lets you also sign in with your email." : "You currently sign in with WhatsApp. Add an email and password to sign in another way and to receive account emails."}</p>
          </div>
          {!email ? (
            <div>
              <label htmlFor="setup-email" className="mb-2 block text-sm font-semibold">Email address</label>
              <input id="setup-email" type="email" autoComplete="email" required value={newEmail} onChange={(event) => setNewEmail(event.target.value)} className={inputClass} />
            </div>
          ) : null}
          <div>
            <label htmlFor="setup-password" className="mb-2 block text-sm font-semibold">Password</label>
            <input id="setup-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={setupPassword} onChange={(event) => setSetupPassword(event.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="setup-confirm" className="mb-2 block text-sm font-semibold">Confirm password</label>
            <input id="setup-confirm" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={setupConfirm} onChange={(event) => setSetupConfirm(event.target.value)} className={inputClass} />
          </div>
          {setupError ? <ErrorNote>{setupError}</ErrorNote> : null}
          {setupNotice ? <SuccessNote>{setupNotice}</SuccessNote> : null}
          <button type="submit" disabled={setupBusy} className={primaryButtonClass}>{setupBusy ? "Saving…" : email ? "Add password" : "Save email and password"}</button>
        </form>
      )}

      <section className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <div><h2 className="text-lg font-bold">Two-factor authentication</h2><p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">Use an authenticator app such as Google Authenticator or Microsoft Authenticator to add a second layer of security.</p></div>
        {totpEnabled ? <p className="text-sm font-semibold text-green-600">Authenticator-based 2FA is enabled.</p> : totpUri ? <form onSubmit={verifyTotpSetup} className="space-y-4">
          <p className="text-sm">Add this account in your authenticator app using the setup key below (or enter the provisioning URI into a QR-code generator).</p>
          <div className="break-all rounded-lg bg-[var(--color-surface-muted)] p-3 text-sm"><strong>Setup key:</strong> {totpSecret}</div>
          <div className="break-all text-xs text-[var(--color-text-muted)]">{totpUri}</div>
          <div><label htmlFor="totp-code" className="mb-2 block text-sm font-semibold">6-digit authenticator code</label><input id="totp-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required value={totpCode} onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))} className={inputClass} /></div>
          {totpError ? <ErrorNote>{totpError}</ErrorNote> : null}<button className={primaryButtonClass} disabled={totpBusy}>{totpBusy ? "Verifying…" : "Verify and enable 2FA"}</button>
        </form> : <button type="button" onClick={startTotpSetup} disabled={totpBusy} className={primaryButtonClass}>{totpBusy ? "Starting…" : "Set up authenticator"}</button>}
        {totpError && !totpUri ? <ErrorNote>{totpError}</ErrorNote> : null}{totpNotice ? <SuccessNote>{totpNotice}</SuccessNote> : null}
      </section>

      <section className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <h2 className="text-lg font-bold">Sign out everywhere</h2>
        <p className="text-sm leading-6 text-[var(--color-text-muted)]">Ends this session and every other one on any device. Use it if you think someone else has access to your account.</p>
        <button type="button" disabled={everywhereBusy} onClick={handleSignOutEverywhere} className="w-full rounded-xl border border-[var(--color-danger)]/40 px-4 py-3.5 text-sm font-bold text-[var(--color-danger)] transition hover:bg-[var(--color-danger)]/10 disabled:cursor-not-allowed disabled:opacity-60">{everywhereBusy ? "Signing out…" : "Sign out of all devices"}</button>
      </section>
    </div>
  );
}
