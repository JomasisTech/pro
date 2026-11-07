"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, getStoredOrganization } from "@/lib/auth";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
export default function BillingReturnPage() {
  const router = useRouter();
  const [status, setStatus] = useState("Verifying your payment with Paystack…");
  const [error, setError] = useState("");
  useEffect(() => {
    const token = getAccessToken(); const organization = getStoredOrganization(); const reference = new URLSearchParams(window.location.search).get("reference");
    if (!token || !organization) { router.replace("/login"); return; }
    if (!reference) { setError("The payment reference is missing. Please return to billing and check your subscription status."); return; }
    let cancelled = false;
    void fetch(`${API_BASE_URL}/api/v1/billing/organizations/${organization.id}/transactions/${encodeURIComponent(reference)}/verify`, {
      method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, cache: "no-store",
    }).then(async (response) => { const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Payment verification failed."); return payload; })
      .then((payload) => { if (!cancelled) setStatus(payload.payment_status === "paid" ? "Payment verified. Your subscription is now active." : "Paystack has not confirmed this payment yet. Your subscription has not been activated."); })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "We could not verify the payment yet."); });
    return () => { cancelled = true; };
  }, [router]);
  return <main className="mx-auto max-w-2xl p-5 py-16"><section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-7 text-center"><div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-[var(--color-brand-soft)] text-2xl text-[var(--color-brand)]">{error ? "!" : "✓"}</div><h1 className="mt-5 text-2xl font-extrabold">Payment status</h1>{error ? <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">{error}</p> : <p role="status" className="mt-3 text-sm text-[var(--color-text-muted)]">{status}</p>}<p className="mt-3 text-xs text-[var(--color-text-muted)]">A browser redirect is not proof of payment. BizPilotPro activates a subscription only after server-side verification.</p><Link href="/billing" className="mt-6 inline-flex rounded-xl bg-[var(--color-brand)] px-5 py-3 text-sm font-bold text-white">Return to billing</Link></section></main>;
}
