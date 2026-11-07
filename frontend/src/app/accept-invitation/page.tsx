"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { acceptOrganizationInvitation, getAccessToken, saveActiveOrganization } from "@/lib/auth";
import { AuthShell, ErrorNote, SuccessNote, primaryButtonClass } from "@/components/auth-shell";

export default function AcceptInvitationPage() {
  const [token, setToken] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") || "");
    setSignedIn(Boolean(getAccessToken()));
  }, []);

  async function accept() {
    const accessToken = getAccessToken();
    if (!accessToken || !token) return;
    setBusy(true);
    setError("");
    try {
      const organization = await acceptOrganizationInvitation(token, accessToken);
      saveActiveOrganization(organization);
      setSuccess(`You have joined ${organization.name} as ${organization.role}.`);
      window.setTimeout(() => window.location.assign("/"), 900);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The invitation could not be accepted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell eyebrow="Workspace invitation" title="Join a workspace" intro="Accept the invitation using the account associated with the invited email address.">
      <div className="space-y-5">
        {!token ? <ErrorNote>This invitation link is missing its token. Ask the workspace owner to send a new invitation.</ErrorNote> : null}
        {!signedIn && token ? <>
          <p className="text-sm leading-6 text-[var(--color-text-muted)]">Sign in or create an account with the email address that received this invitation, then return to this link.</p>
          <Link href={`/login?next=${encodeURIComponent(`/accept-invitation?token=${token}`)}`} className={primaryButtonClass}>Sign in to accept</Link>
          <Link href={`/register?next=${encodeURIComponent(`/accept-invitation?token=${token}`)}`} className="block text-center text-sm font-bold text-[var(--auth-accent)] hover:underline">Create an account</Link>
        </> : null}
        {signedIn && token ? <button type="button" onClick={() => void accept()} disabled={busy || Boolean(success)} className={primaryButtonClass}>{busy ? "Accepting invitation…" : "Accept invitation"}</button> : null}
        {error ? <ErrorNote>{error}</ErrorNote> : null}
        {success ? <SuccessNote>{success}</SuccessNote> : null}
        <Link href="/" className="block text-center text-sm text-[var(--color-text-muted)] hover:underline">Return to dashboard</Link>
      </div>
    </AuthShell>
  );
}
