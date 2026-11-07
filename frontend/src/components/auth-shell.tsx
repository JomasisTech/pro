import Link from "next/link";
import type { ReactNode } from "react";

export const inputClass =
  "auth-input w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3.5 text-base outline-none transition focus:border-[var(--auth-accent)] focus:ring-2 focus:ring-[var(--auth-accent)]/20";
export const primaryButtonClass =
  "auth-submit w-full rounded-xl px-4 py-3.5 text-sm font-bold shadow-sm transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60";

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div role="alert" className="auth-alert-error rounded-xl px-4 py-3 text-sm leading-5">{children}</div>;
}

export function SuccessNote({ children }: { children: ReactNode }) {
  return <div role="status" className="auth-alert-success rounded-xl px-4 py-3 text-sm leading-5">{children}</div>;
}

/** Shared purple-glass shell for signed-out account, recovery, verification, and WhatsApp sign-in pages. */
export function AuthShell({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: string; children: ReactNode }) {
  return (
    <main className="auth-page min-h-screen px-4 py-8 text-white sm:px-6">
      <div className="auth-centered-shell mx-auto flex min-h-[calc(100svh-4rem)] w-full max-w-lg items-center justify-center">
        <section className="auth-card auth-form-panel w-full rounded-[2rem] p-6 sm:p-10">
          <div className="mx-auto w-full max-w-md">
            <Link href="/login" className="mb-8 flex items-center gap-3" aria-label="AutoBizPro — back to sign in">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-xl font-black text-[#5b21b6]">A</span>
              <span className="text-xl font-extrabold tracking-tight text-white">AutoBiz<span className="text-violet-200">Pro</span><span className="mt-0.5 block text-[10px] font-normal text-white/70">Automate · Grow · Succeed</span></span>
            </Link>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-violet-200">{eyebrow}</p>
            <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-white">{title}</h1>
            <p className="mt-3 text-sm leading-6 text-[var(--auth-form-muted)]">{intro}</p>
            <div className="mt-8">{children}</div>
          </div>
        </section>
      </div>
    </main>
  );
}
