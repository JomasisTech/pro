"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getAccessToken,
  getStoredOrganization,
  getStoredUser,
  hasPlaceholderName,
  type AuthOrganization,
  type AuthUser,
} from "@/lib/auth";
import { fetchBusinessProfile, onboardingSkipped, skipOnboarding } from "@/lib/profile";

type Missing = { business: boolean; name: boolean };

/**
 * A gentle, never-blocking nudge for people whose account was created through Google or WhatsApp (or who
 * skipped onboarding): a slim banner while the business profile is missing, plus an optional one-time
 * pop-up on the dashboard. Nothing here stops anyone from using the app.
 */
export function ProfileCompletionPrompt({
  organization,
  user,
  showModal = false,
}: {
  organization?: AuthOrganization | null;
  user?: AuthUser | null;
  showModal?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [missing, setMissing] = useState<Missing | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const orgId = organization?.id;

  useEffect(() => {
    const token = getAccessToken();
    const active = organization ?? getStoredOrganization();
    if (!token || !active || (active.role !== "owner" && active.role !== "admin")) {
      setMissing(null);
      return;
    }
    let cancelled = false;
    fetchBusinessProfile(token, active.id)
      .then((profile) => {
        if (cancelled) return;
        const needsName = hasPlaceholderName(user ?? getStoredUser());
        const next = { business: profile === null, name: needsName };
        setMissing(next.business || next.name ? next : null);
        if (showModal && (next.business || next.name) && !onboardingSkipped(active.id)) setModalOpen(true);
      })
      .catch(() => {
        if (!cancelled) setMissing(null); // never nag because of a network error
      });
    return () => {
      cancelled = true;
    };
    // Re-check on navigation so the banner disappears once the profile has been saved.
  }, [orgId, pathname, organization, user, showModal]);

  useEffect(() => {
    if (!modalOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") dismissModal();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modalOpen]);

  function dismissModal() {
    const active = organization ?? getStoredOrganization();
    if (active) skipOnboarding(active.id); // "remind me later": no pop-up again this session, the banner stays
    setModalOpen(false);
  }

  if (!missing || pathname === "/profile") return null;

  const items: string[] = [];
  if (missing.business) items.push("your business name, industry and what you sell");
  if (missing.name) items.push("your name");
  const summary = items.join(" and ");
  const target = missing.business ? "/onboarding" : "/security";

  return (
    <>
      <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-4 py-3 text-sm">
        <p className="min-w-0 flex-1 leading-6">
          <strong className="font-bold">Finish setting up your account.</strong> Add {summary} so AutoBizPro can tailor your content.
        </p>
        <Link href={target} className="shrink-0 rounded-lg px-3.5 py-2 text-xs font-bold hover:opacity-90" style={{ backgroundColor: "var(--brand-solid)", color: "#fff" }}>Complete now</Link>
      </div>

      {modalOpen ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/45 p-4" onClick={dismissModal}>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="profile-prompt-title"
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl sm:p-7"
          >
            <p className="text-[11px] font-bold uppercase tracking-widest text-[var(--color-brand)]">Welcome to AutoBizPro</p>
            <h2 id="profile-prompt-title" className="mt-2 text-xl font-extrabold tracking-tight">Tell us about your business</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">
              You&apos;re signed in. To get content that sounds like your brand, add {summary}. It only takes a couple of minutes, and you can do it later.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button type="button" onClick={dismissModal} className="rounded-xl border border-[var(--color-border)] px-4 py-3 text-sm font-semibold hover:bg-[var(--color-surface-raised)]">Remind me later</button>
              <button type="button" autoFocus onClick={() => { setModalOpen(false); router.push(target); }} className="rounded-xl px-4 py-3 text-sm font-bold hover:opacity-90" style={{ backgroundColor: "var(--brand-solid)", color: "#fff" }}>Complete now</button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
