"use client";

import { Select } from "@/components/select";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { getAccessToken, getStoredOrganization, isPlaceholderWorkspaceName, renameWorkspace, saveActiveOrganization, type AuthOrganization } from "@/lib/auth";
import {
  fetchBusinessProfile,
  fetchCategories,
  saveBusinessProfile,
  skipOnboarding,
  type BusinessProfileInput,
  type Category,
} from "@/lib/profile";

const EMPTY_FORM: BusinessProfileInput = {
  business_name: "",
  industry_id: null,
  niche: null,
  subcategory_id: null,
  description: null,
  products_services: null,
  location: null,
  target_audience: null,
  audience_type: null,
  geographic_market: null,
  unique_selling_points: null,
  brand_voice: null,
  preferred_tone: null,
  preferred_words: null,
  avoided_words: null,
  brand_voice_mode: "hybrid",
  custom_ai_instructions: null,
  language: "en",
  marketing_goals: null,
  posting_frequency: null,
};

const FREQUENCIES = ["Daily", "3–5 times a week", "1–2 times a week", "A few times a month"];

const inputClass =
  "w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-base outline-none transition focus:border-[var(--auth-accent)] focus:ring-2 focus:ring-[var(--auth-accent)]/20 disabled:opacity-60";

export default function OnboardingPage() {
  const router = useRouter();
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<BusinessProfileInput>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const canEdit = organization?.role === "owner" || organization?.role === "admin";
  const subcategories = categories.find((item) => item.id === form.industry_id)?.subcategories ?? [];

  useEffect(() => {
    const token = getAccessToken();
    const active = getStoredOrganization();
    if (!token || !active) {
      router.replace("/login");
      return;
    }
    setOrganization(active);
    let cancelled = false;
    (async () => {
      try {
        const [loadedCategories, profile] = await Promise.all([
          fetchCategories(token),
          fetchBusinessProfile(token, active.id),
        ]);
        if (cancelled) return;
        setCategories(loadedCategories);
        if (profile) {
          const { organization_id: _organizationId, updated_at: _updatedAt, profile_version: _profileVersion, confirmed_at: _confirmedAt, onboarding_completed_at: _completedAt, ...editable } = profile;
          void _organizationId;
          void _updatedAt;
          void _profileVersion;
          void _confirmedAt;
          void _completedAt;
          setForm(editable);
        } else {
          // A generic workspace name made by social sign-in is not a business name; make them type the real one.
          setForm({ ...EMPTY_FORM, business_name: isPlaceholderWorkspaceName(active.name) ? "" : active.name });
        }
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Something went wrong. Please try again.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function setText(field: keyof BusinessProfileInput, value: string) {
    setSaved(false);
    setForm((current) => ({ ...current, [field]: value === "" && field !== "business_name" && field !== "language" ? null : value }));
  }

  function chooseIndustry(value: string) {
    setSaved(false);
    setForm((current) => ({ ...current, industry_id: value || null, subcategory_id: null }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getAccessToken();
    if (!token || !organization) {
      router.replace("/login");
      return;
    }
    setError("");
    setSaved(false);
    setBusy(true);
    try {
      if (!form.industry_id || !form.niche?.trim()) {
        setError("Please select your industry and enter your business niche.");
        return;
      }
      await saveBusinessProfile(token, organization.id, form);
      if (organization.role === "owner" && isPlaceholderWorkspaceName(organization.name) && form.business_name.trim()) {
        // Give the auto-named workspace its real name. Best effort: the profile is already saved.
        try {
          saveActiveOrganization(await renameWorkspace(token, organization.id, form.business_name.trim()));
        } catch {
          // Leave the generic name; it can be renamed from Workspace settings.
        }
      }
      setSaved(true);
      router.push("/profile");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't save the profile. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[var(--color-page)] px-4 py-8 text-[var(--color-text)] sm:px-6">
      <div className="mx-auto w-full max-w-2xl">
        <Link href="/" className="text-sm font-bold text-[var(--color-brand)] hover:underline">← Back to dashboard</Link>
        <div className="mt-4 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl sm:p-10">
          <p className="text-sm font-bold text-[var(--color-brand)]">BUSINESS PROFILE</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight">Tell us about {organization && !isPlaceholderWorkspaceName(organization.name) ? organization.name : "your business"}</h1>
          <p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">This helps AutoBizPro understand your business and tailor its marketing assistance. You can edit it any time.</p>

          {loading ? (
            <p className="mt-8 text-sm text-[var(--color-text-muted)]">Loading…</p>
          ) : (
            <form onSubmit={handleSubmit} className="mt-8 space-y-5">
              {!canEdit ? <div role="status" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm">Only workspace owners and admins can edit the business profile.</div> : null}
              <div>
                <label htmlFor="business_name" className="mb-2 block text-sm font-semibold">Business name</label>
                <input id="business_name" required minLength={2} maxLength={160} disabled={!canEdit} value={form.business_name} onChange={(event) => setText("business_name", event.target.value)} className={inputClass} />
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="industry" className="mb-2 block text-sm font-semibold">Industry <span aria-hidden="true">*</span></label>
                  <Select id="industry" required disabled={!canEdit} value={form.industry_id ?? ""} onChange={(event) => chooseIndustry(event.target.value)} className={inputClass}>
                    <option value="">Select an industry</option>
                    {categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </Select>
                </div>
                <div>
                  <label htmlFor="subcategory" className="mb-2 block text-sm font-semibold">Subcategory</label>
                  <Select id="subcategory" disabled={!canEdit || subcategories.length === 0} value={form.subcategory_id ?? ""} onChange={(event) => setText("subcategory_id", event.target.value)} className={inputClass}>
                    <option value="">{subcategories.length === 0 ? "Choose an industry first" : "Select a subcategory"}</option>
                    {subcategories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </Select>
                </div>
              </div>
              <div>
                <label htmlFor="niche" className="mb-2 block text-sm font-semibold">Business niche <span aria-hidden="true">*</span></label>
                <input id="niche" required minLength={2} maxLength={160} disabled={!canEdit} value={form.niche ?? ""} onChange={(event) => setText("niche", event.target.value)} placeholder="e.g. custom bridal wear, vegan bakery, business coaching" className={inputClass} />
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">Be specific. Your niche helps the AI understand your market even if you have no social media posts yet.</p>
              </div>
              <div>
                <label htmlFor="description" className="mb-2 block text-sm font-semibold">What does your business do?</label>
                <textarea id="description" rows={3} maxLength={2000} disabled={!canEdit} value={form.description ?? ""} onChange={(event) => setText("description", event.target.value)} className={inputClass} />
              </div>
              <div>
                <label htmlFor="products_services" className="mb-2 block text-sm font-semibold">Products or services</label>
                <textarea id="products_services" rows={3} maxLength={2000} disabled={!canEdit} value={form.products_services ?? ""} onChange={(event) => setText("products_services", event.target.value)} className={inputClass} />
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="location" className="mb-2 block text-sm font-semibold">Location</label>
                  <input id="location" maxLength={160} disabled={!canEdit} value={form.location ?? ""} onChange={(event) => setText("location", event.target.value)} className={inputClass} />
                </div>
                <div>
                  <label htmlFor="language" className="mb-2 block text-sm font-semibold">Content language</label>
                  <input id="language" required minLength={2} maxLength={35} disabled={!canEdit} value={form.language} onChange={(event) => setText("language", event.target.value)} placeholder="en" className={inputClass} />
                </div>
              </div>
              <div>
                <label htmlFor="target_audience" className="mb-2 block text-sm font-semibold">Target audience</label>
                <textarea id="target_audience" rows={2} maxLength={1000} disabled={!canEdit} value={form.target_audience ?? ""} onChange={(event) => setText("target_audience", event.target.value)} placeholder="Who are your ideal customers?" className={inputClass} />
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="audience_type" className="mb-2 block text-sm font-semibold">Who do you sell to?</label>
                  <Select id="audience_type" disabled={!canEdit} value={form.audience_type ?? ""} onChange={(event) => setForm((current) => ({ ...current, audience_type: event.target.value ? event.target.value as "consumers" | "businesses" | "both" : null }))} className={inputClass}>
                    <option value="">Select an audience</option>
                    <option value="consumers">Individual customers</option>
                    <option value="businesses">Businesses</option>
                    <option value="both">Both</option>
                  </Select>
                </div>
                <div>
                  <label htmlFor="geographic_market" className="mb-2 block text-sm font-semibold">Main market / area served</label>
                  <input id="geographic_market" maxLength={160} disabled={!canEdit} value={form.geographic_market ?? ""} onChange={(event) => setText("geographic_market", event.target.value)} placeholder="e.g. Lagos, Nigeria; worldwide" className={inputClass} />
                </div>
              </div>
              <div>
                <label htmlFor="unique_selling_points" className="mb-2 block text-sm font-semibold">What makes your business different?</label>
                <textarea id="unique_selling_points" rows={2} maxLength={1500} disabled={!canEdit} value={form.unique_selling_points ?? ""} onChange={(event) => setText("unique_selling_points", event.target.value)} placeholder="Your strengths, special process or unique value" className={inputClass} />
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="brand_voice" className="mb-2 block text-sm font-semibold">Brand voice</label>
                  <input id="brand_voice" maxLength={500} disabled={!canEdit} value={form.brand_voice ?? ""} onChange={(event) => setText("brand_voice", event.target.value)} placeholder="Friendly, professional, playful…" className={inputClass} />
                </div>
                <div>
                  <label htmlFor="preferred_tone" className="mb-2 block text-sm font-semibold">Preferred writing tone</label>
                  <input id="preferred_tone" maxLength={120} disabled={!canEdit} value={form.preferred_tone ?? ""} onChange={(event) => setText("preferred_tone", event.target.value)} placeholder="Warm, confident, conversational…" className={inputClass} />
                </div>
              </div>
              <section className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4 sm:p-5">
                <div>
                  <h2 className="text-base font-bold">AI brand voice controls</h2>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">Choose how AutoBizPro learns your communication style. Your confirmed business facts always remain under your control.</p>
                </div>
                <div>
                  <label htmlFor="brand_voice_mode" className="mb-2 block text-sm font-semibold">Brand voice source</label>
                  <Select id="brand_voice_mode" disabled={!canEdit} value={form.brand_voice_mode} onChange={(event) => setForm((current) => ({ ...current, brand_voice_mode: event.target.value as BusinessProfileInput["brand_voice_mode"] }))} className={inputClass}>
                    <option value="hybrid">Hybrid — learn from social accounts and apply my instructions</option>
                    <option value="automatic">Automatic — use approved social-media voice analysis</option>
                    <option value="manual">Manual — use only the voice settings I provide</option>
                  </Select>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">Social analysis is used only after an owner or admin approves it. It never overwrites your industry, niche or other business facts.</p>
                </div>
                <div>
                  <label htmlFor="custom_ai_instructions" className="mb-2 block text-sm font-semibold">Additional AI instructions</label>
                  <textarea id="custom_ai_instructions" rows={3} maxLength={2000} disabled={!canEdit} value={form.custom_ai_instructions ?? ""} onChange={(event) => setText("custom_ai_instructions", event.target.value)} placeholder="e.g. Use simple English, avoid slang, keep emojis minimal, and respond empathetically to complaints." className={inputClass} />
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">These preferences guide generated drafts. Review every draft before publishing.</p>
                </div>
                {canEdit ? <div className="flex flex-col gap-2 border-t border-[var(--color-border)] pt-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-[var(--color-text-muted)]">Want AutoBizPro to rely on the latest approved social-media voice analysis instead?</p>
                  <button type="button" onClick={() => {
                    if (!window.confirm("Switch to AI suggestions? This clears your custom brand voice, preferred tone, preferred/avoided phrases and additional AI instructions. Your business facts will remain unchanged. Save the profile to apply this change.")) return;
                    setSaved(false);
                    setForm((current) => ({ ...current, brand_voice_mode: "automatic", brand_voice: null, preferred_tone: null, preferred_words: null, avoided_words: null, custom_ai_instructions: null }));
                  }} className="shrink-0 rounded-xl border border-[var(--color-border)] px-3 py-2 text-xs font-semibold hover:border-[var(--color-brand)]">Reset to AI suggestions</button>
                </div> : null}
              </section>
              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="preferred_words" className="mb-2 block text-sm font-semibold">Words or phrases to use</label>
                  <textarea id="preferred_words" rows={2} maxLength={1000} disabled={!canEdit} value={form.preferred_words ?? ""} onChange={(event) => setText("preferred_words", event.target.value)} className={inputClass} />
                </div>
                <div>
                  <label htmlFor="avoided_words" className="mb-2 block text-sm font-semibold">Words or phrases to avoid</label>
                  <textarea id="avoided_words" rows={2} maxLength={1000} disabled={!canEdit} value={form.avoided_words ?? ""} onChange={(event) => setText("avoided_words", event.target.value)} className={inputClass} />
                </div>
              </div>
              <div>
                <label htmlFor="marketing_goals" className="mb-2 block text-sm font-semibold">Marketing goals</label>
                <textarea id="marketing_goals" rows={2} maxLength={1000} disabled={!canEdit} value={form.marketing_goals ?? ""} onChange={(event) => setText("marketing_goals", event.target.value)} className={inputClass} />
              </div>
              <div>
                <label htmlFor="posting_frequency" className="mb-2 block text-sm font-semibold">Preferred posting frequency</label>
                <Select id="posting_frequency" disabled={!canEdit} value={form.posting_frequency ?? ""} onChange={(event) => setText("posting_frequency", event.target.value)} className={inputClass}>
                  <option value="">Not sure yet</option>
                  {FREQUENCIES.map((item) => <option key={item} value={item}>{item}</option>)}
                </Select>
              </div>
              {error ? <div role="alert" className="rounded-xl border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 px-4 py-3 text-sm leading-5 text-[var(--color-danger)]">{error}</div> : null}
              {saved ? <div role="status" className="rounded-xl border border-[var(--color-success)]/30 bg-[var(--color-success)]/10 px-4 py-3 text-sm leading-5 text-[var(--color-success)]">Profile saved.</div> : null}
              <button type="submit" disabled={busy || !canEdit} className="w-full rounded-xl bg-[var(--color-brand)] px-4 py-3.5 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60">{busy ? "Saving…" : "Save profile"}</button>
              {!canEdit || !organization ? null : (
                <button type="button" onClick={() => { skipOnboarding(organization.id); router.push("/"); }} className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)]">Skip for now</button>
              )}
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
