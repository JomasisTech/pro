"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthResponse, getApiBaseUrl, saveAuthSession } from "@/lib/auth";

export default function SocialAuthCallbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState("Completing your sign-in…");
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("access_token");
    if (!token) {
      setMessage("We couldn't complete sign-in. Please return to the login page and try again.");
      return;
    }
    const apiBase = getApiBaseUrl();
    const headers = { Authorization: `Bearer ${token}` };
    Promise.all([
      fetch(`${apiBase}/api/v1/auth/me`, { headers, cache: "no-store" }),
      fetch(`${apiBase}/api/v1/organizations`, { headers, cache: "no-store" }),
    ]).then(async ([userResponse, orgResponse]) => {
      if (!userResponse.ok || !orgResponse.ok) throw new Error("Your sign-in session could not be verified.");
      const user = await userResponse.json();
      const organizations = await orgResponse.json();
      if (!organizations.length) throw new Error("No workspace is associated with this account.");
      saveAuthSession({ access_token: token, token_type: "bearer", user, organization: organizations[0] } as AuthResponse);
      window.history.replaceState(null, "", window.location.pathname);
      router.replace("/");
    }).catch((error: unknown) => setMessage(error instanceof Error ? error.message : "Sign-in failed."));
  }, [router]);
  return <main className="flex min-h-screen items-center justify-center bg-[var(--color-page)] px-6 text-center text-[var(--color-text)]"><div className="max-w-md"><p className="text-lg font-semibold">{message}</p><Link href="/login" className="mt-5 inline-block text-sm font-bold text-[var(--auth-accent)] hover:underline">Back to login</Link></div></main>;
}
