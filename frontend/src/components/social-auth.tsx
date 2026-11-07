"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchAuthProviders, getApiBaseUrl, type AuthProviders } from "@/lib/auth";

const buttonClass =
  "auth-social-button flex w-full items-center justify-center gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3.5 text-sm font-bold transition hover:bg-[var(--color-page)]";

/**
 * "Continue with Google / WhatsApp" buttons plus the "or" divider.
 * Only the providers this deployment has configured are shown; when there are none this renders nothing,
 * so the page falls back to the plain email form with no stray divider or gap.
 */
export function SocialSignInButtons({ action = "Continue" }: { action?: "Continue" | "Sign up" }) {
  const [providers, setProviders] = useState<AuthProviders | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchAuthProviders().then((result) => {
      if (!cancelled) setProviders(result);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!providers || (!providers.google && !providers.whatsapp)) return null;
  const verb = action === "Sign up" ? "Sign up" : "Continue";

  return (
    <>
      <div className="space-y-3">
        {providers.google ? (
          <a href={`${getApiBaseUrl()}/api/v1/auth/google`} className={buttonClass}>
            <GoogleMark />
            {verb} with Google
          </a>
        ) : null}
        {providers.whatsapp ? (
          <Link href="/whatsapp-login" className={buttonClass}>
            <WhatsAppMark />
            {verb} with WhatsApp
          </Link>
        ) : null}
      </div>
      <div className="auth-social-divider my-6 flex items-center gap-3 text-xs">
        <span className="h-px flex-1 bg-[var(--color-border)]" />
        <span>OR USE EMAIL</span>
        <span className="h-px flex-1 bg-[var(--color-border)]" />
      </div>
    </>
  );
}

/** Messages for the `?social_error=` codes the API appends when a social sign-in fails. */
export function socialErrorMessage(code: string | null): string {
  switch (code) {
    case "email_exists":
      return "An account with this email already exists. Please sign in with your email and password (use “Forgot password?” if you need to).";
    case "google_unavailable":
      return "Google sign-in isn't available right now. Please use your email and password.";
    case "google":
      return "Google sign-in could not be completed. Please try again or use your email and password.";
    default:
      return code ? "Sign-in could not be completed. Please try again." : "";
  }
}

export function GoogleMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 48 48" className="h-5 w-5">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.73 7.18l7.26 5.63c4.24-3.91 7.51-9.69 7.51-17.28Z" />
      <path fill="#FBBC05" d="M10.54 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.9 23.9 0 0 0 0 24c0 3.88.93 7.55 2.56 10.78l7.98-6.19Z" />
      <path fill="#34A853" d="M24 48c6.47 0 11.9-2.13 15.86-5.79l-7.26-5.63c-2.02 1.35-4.6 2.15-8.6 2.15-6.26 0-11.57-4.22-13.46-9.91l-7.98 6.19C6.51 43.62 14.62 48 24 48Z" />
    </svg>
  );
}

export function WhatsAppMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5">
      <path
        fill="#25D366"
        d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.9 9.9 0 0 0 4.74 1.21c5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2Zm0 18.15c-1.48 0-2.93-.4-4.2-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24 4.54 0 8.24 3.7 8.24 8.24s-3.7 8.24-8.24 8.24Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.12-.16.25-.64.81-.78.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.12-.14.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.4-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.28Z"
      />
    </svg>
  );
}
