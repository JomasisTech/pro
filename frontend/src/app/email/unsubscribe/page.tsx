"use client";

import { useEffect, useState } from "react";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function EmailUnsubscribePage() {
  const [state, setState] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Processing your request…");

  useEffect(() => {
    let active = true;
    const token = new URLSearchParams(window.location.search).get("token") || "";
    if (!token) { setState("error"); setMessage("This unsubscribe link is incomplete."); return; }
    fetch(`${API}/api/v1/platform-admin/public/email/unsubscribe?token=${encodeURIComponent(token)}`, { method: "POST", cache: "no-store" })
      .then(async response => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "We could not process this request.");
        if (active) { setState("success"); setMessage(body.message || "You have been unsubscribed."); }
      })
      .catch(error => { if (active) { setState("error"); setMessage(error instanceof Error ? error.message : "We could not process this request."); } });
    return () => { active = false; };
  }, []);

  return <main className="flex min-h-screen items-center justify-center bg-[var(--page)] px-5 py-12"><section className="w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--surface)] p-7 text-center"><h1 className="text-xl font-bold">Email preferences</h1><p className="mt-3 text-sm text-[var(--text-muted)]">{message}</p>{state === "success" && <p className="mt-4 text-xs text-[var(--text-muted)]">You may still receive essential account and security messages.</p>}</section></main>;
}
