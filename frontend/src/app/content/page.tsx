"use client";

import { Select } from "@/components/select";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { getAccessToken, getStoredOrganization, getStoredUserId, type AuthOrganization } from "@/lib/auth";
import {
  createDraft,
  deleteDraft,
  fetchDrafts,
  fetchUsage,
  generateCaption,
  generateVideoScript,
  type VideoPlatform,
  type VideoStyle,
  updateDraft,
  type ContentType,
  type Draft,
  type DraftStatus,
  type Usage,
  DRAFT_PAGE_SIZE,
} from "@/lib/content";

const CONTENT_TYPES: Array<{ value: ContentType; label: string }> = [
  { value: "general", label: "General post" },
  { value: "promotion", label: "Promotion" },
  { value: "educational", label: "Educational" },
  { value: "product", label: "Product / service" },
];

const inputClass =
  "w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-base outline-none transition focus:border-[var(--auth-accent)] focus:ring-2 focus:ring-[var(--auth-accent)]/20 disabled:opacity-60";
const primaryButton =
  "rounded-xl bg-[var(--color-brand)] px-4 py-3 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60";
const secondaryButton =
  "rounded-xl border border-[var(--color-border)] px-3 py-2 text-xs font-semibold transition hover:bg-[var(--color-surface-raised)] disabled:cursor-not-allowed disabled:opacity-60";

export default function ContentPage() {
  const router = useRouter();
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [topic, setTopic] = useState("");
  const [contentType, setContentType] = useState<ContentType>("general");
  const [caption, setCaption] = useState("");
  const [mode, setMode] = useState<"caption" | "video">("caption");
  const [videoPlatform, setVideoPlatform] = useState<VideoPlatform>("tiktok");
  const [videoStyle, setVideoStyle] = useState<VideoStyle>("educational");
  const [videoDuration, setVideoDuration] = useState(30);
  const [callToAction, setCallToAction] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  const canApprove = organization?.role === "owner" || organization?.role === "admin";
  const captionUsage = usage?.metrics.find((item) => item.metric === "ai_captions");
  const videoUsage = usage?.metrics.find((item) => item.metric === "ai_video_scripts");

  const refreshUsage = useCallback(async (token: string, orgId: string) => {
    try {
      setUsage(await fetchUsage(token, orgId));
    } catch {
      // The usage banner is informational; failing to load it must not block the page.
    }
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    const active = getStoredOrganization();
    if (!token || !active) {
      router.replace("/login");
      return;
    }
    setOrganization(active);
    setCurrentUserId(getStoredUserId());
    let cancelled = false;
    (async () => {
      try {
        const [loadedDrafts, loadedUsage] = await Promise.all([fetchDrafts(token, active.id), fetchUsage(token, active.id).catch(() => null)]);
        if (cancelled) return;
        setDrafts(loadedDrafts);
        setHasMore(loadedDrafts.length === DRAFT_PAGE_SIZE);
        setUsage(loadedUsage);
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

  async function run(label: string, action: (token: string, orgId: string) => Promise<void>) {
    const token = getAccessToken();
    if (!token || !organization) {
      router.replace("/login");
      return;
    }
    setError("");
    setBusy(label);
    try {
      await action(token, organization.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Something went wrong. Please try again.");
    } finally {
      setBusy("");
    }
  }

  function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run("generate", async (token, orgId) => {
      if (mode === "video") {
        const result = await generateVideoScript(token, orgId, { topic: topic.trim(), platform: videoPlatform, duration_seconds: videoDuration, style: videoStyle, call_to_action: callToAction.trim() || undefined });
        setCaption(result.script);
      } else {
        const result = await generateCaption(token, orgId, topic.trim(), contentType);
        setCaption(result.caption);
      }
      await refreshUsage(token, orgId);
    });
  }

  function handleSaveDraft() {
    void run("save", async (token, orgId) => {
      const saved = await createDraft(token, orgId, caption, topic.trim(), mode === "video" ? "video_script" : contentType);
      setDrafts((current) => [saved, ...current]);
      setCaption("");
    });
  }

  function handleSaveEdit(draft: Draft) {
    void run(`edit-${draft.id}`, async (token, orgId) => {
      const saved = await updateDraft(token, orgId, draft.id, { content: editText });
      setDrafts((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      setEditingId(null);
    });
  }

  function handleStatus(draft: Draft, status: DraftStatus) {
    void run(`status-${draft.id}`, async (token, orgId) => {
      const saved = await updateDraft(token, orgId, draft.id, { status });
      setDrafts((current) => current.map((item) => (item.id === saved.id ? saved : item)));
    });
  }

  function handleLoadMore() {
    void run("load-more", async (token, orgId) => {
      const next = await fetchDrafts(token, orgId, drafts.length);
      setDrafts((current) => [...current, ...next.filter((item) => !current.some((existing) => existing.id === item.id))]);
      setHasMore(next.length === DRAFT_PAGE_SIZE);
    });
  }

  function handleDelete(draft: Draft) {
    if (!window.confirm("Delete this draft? This cannot be undone.")) return;
    void run(`delete-${draft.id}`, async (token, orgId) => {
      await deleteDraft(token, orgId, draft.id);
      setDrafts((current) => current.filter((item) => item.id !== draft.id));
    });
  }

  const activeUsage = mode === "video" ? videoUsage : captionUsage;
  const limitReached = activeUsage?.remaining === 0;

  return (
    <main className="min-h-screen bg-[var(--color-page)] px-4 py-8 text-[var(--color-text)] sm:px-6">
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <Link href="/" className="text-sm font-bold text-[var(--color-brand)] hover:underline">← Back to dashboard</Link>

        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl sm:p-8">
          <p className="text-sm font-bold text-[var(--color-brand)]">CONTENT STUDIO</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight">Content & Video Studio</h1>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">Create brand-aware captions or ready-to-record video scripts for your social channels.</p>
          <div className="mt-5 grid grid-cols-2 gap-2 rounded-xl bg-[var(--color-surface-raised)] p-1">
            <button type="button" onClick={() => setMode("caption")} className={`rounded-lg px-3 py-2 text-sm font-bold ${mode === "caption" ? "bg-[var(--color-brand)] text-white" : ""}`}>Caption</button>
            <button type="button" onClick={() => setMode("video")} className={`rounded-lg px-3 py-2 text-sm font-bold ${mode === "video" ? "bg-[var(--color-brand)] text-white" : ""}`}>Video script</button>
          </div>
          {activeUsage ? (
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">
              {usage?.plan_name} plan:{" "}
              {activeUsage.limit === null ? "unlimited" : `${activeUsage.used} of ${activeUsage.limit}`} {activeUsage.label} used this month.
            </p>
          ) : null}

          <form onSubmit={handleGenerate} className="mt-6 space-y-4">
            <div>
              <label htmlFor="topic" className="mb-2 block text-sm font-semibold">What is the post about?</label>
              <input id="topic" required minLength={2} maxLength={300} value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="New sourdough loaves this weekend" className={inputClass} />
            </div>
            {mode === "caption" ? <div>
              <label htmlFor="content_type" className="mb-2 block text-sm font-semibold">Type of post</label>
              <Select id="content_type" value={contentType} onChange={(event) => setContentType(event.target.value as ContentType)} className={inputClass}>
                {CONTENT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </Select>
            </div> : <div className="grid gap-4 sm:grid-cols-2">
              <div><label htmlFor="video_platform" className="mb-2 block text-sm font-semibold">Publish destination</label><Select id="video_platform" value={videoPlatform} onChange={(event) => setVideoPlatform(event.target.value as VideoPlatform)} className={inputClass}><option value="tiktok">TikTok</option><option value="instagram_reels">Instagram Reels</option><option value="facebook_reels">Facebook Reels</option><option value="youtube_shorts">YouTube Shorts</option><option value="youtube_long">YouTube long-form</option></Select></div>
              <div><label htmlFor="video_duration" className="mb-2 block text-sm font-semibold">Target duration</label><Select id="video_duration" value={videoDuration} onChange={(event) => setVideoDuration(Number(event.target.value))} className={inputClass}><option value={15}>15 seconds</option><option value={30}>30 seconds</option><option value={45}>45 seconds</option><option value={60}>60 seconds</option><option value={90}>90 seconds</option><option value={180}>3 minutes</option><option value={300}>5 minutes</option><option value={600}>10 minutes</option></Select></div>
              <div><label htmlFor="video_style" className="mb-2 block text-sm font-semibold">Video style</label><Select id="video_style" value={videoStyle} onChange={(event) => setVideoStyle(event.target.value as VideoStyle)} className={inputClass}><option value="educational">Educational / how-to</option><option value="storytelling">Storytelling</option><option value="product_demo">Product demonstration</option><option value="behind_the_scenes">Behind the scenes</option><option value="testimonial_style">Customer-story format (fiction-free)</option><option value="entertaining">Entertaining</option></Select></div>
              <div><label htmlFor="video_cta" className="mb-2 block text-sm font-semibold">Call to action (optional)</label><input id="video_cta" maxLength={180} value={callToAction} onChange={(event) => setCallToAction(event.target.value)} placeholder="e.g. Send us a message to order" className={inputClass}/></div>
            </div>}
            <button type="submit" disabled={busy !== "" || limitReached} className={`${primaryButton} w-full`}>{busy === "generate" ? "Generating…" : mode === "video" ? "Generate video script" : "Generate caption"}</button>
            {limitReached ? <p className="text-sm text-[var(--color-warning)]">You have used all {activeUsage?.label} for this month on the {usage?.plan_name} plan.</p> : null}
          </form>

          {caption ? (
            <div className="mt-6 space-y-3">
              <label htmlFor="caption" className="block text-sm font-semibold">{mode === "video" ? "Your video script (edit before recording)" : "Your caption (edit it if you like)"}</label>
              <textarea id="caption" rows={mode === "video" ? 16 : 6} maxLength={12000} value={caption} onChange={(event) => setCaption(event.target.value)} className={inputClass} />
              <button type="button" onClick={handleSaveDraft} disabled={busy !== "" || caption.trim() === ""} className={`${primaryButton} w-full`}>{busy === "save" ? "Saving…" : "Save as draft"}</button>
            </div>
          ) : null}

          {error ? <div role="alert" className="mt-4 rounded-xl border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 px-4 py-3 text-sm leading-5 text-[var(--color-danger)]">{error}</div> : null}
        </section>

        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl sm:p-8">
          <h2 className="text-xl font-extrabold">Saved drafts</h2>
          {loading ? (
            <p className="mt-4 text-sm text-[var(--color-text-muted)]">Loading…</p>
          ) : drafts.length === 0 ? (
            <p className="mt-4 text-sm text-[var(--color-text-muted)]">No drafts yet. Generate a caption and save it here.</p>
          ) : (
            <ul className="mt-4 space-y-4">
              {drafts.map((draft) => (
                <li key={draft.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
                  <div className="flex items-center justify-between gap-3 text-xs text-[var(--color-text-muted)]">
                    <span className="truncate">{draft.topic || "No topic"}</span>
                    <span className="rounded-full bg-[var(--color-brand-soft)] px-2.5 py-1 font-bold capitalize text-[var(--color-brand)]">{draft.status}</span>
                  </div>
                  {editingId === draft.id ? (
                    <div className="mt-3 space-y-3">
                      <textarea aria-label="Edit draft text" rows={5} maxLength={12000} value={editText} onChange={(event) => setEditText(event.target.value)} className={inputClass} />
                      <div className="flex gap-2">
                        <button type="button" onClick={() => handleSaveEdit(draft)} disabled={busy !== "" || editText.trim() === ""} className={secondaryButton}>Save</button>
                        <button type="button" onClick={() => setEditingId(null)} className={secondaryButton}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{draft.content}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button type="button" onClick={() => { setEditingId(draft.id); setEditText(draft.content); }} disabled={busy !== ""} className={secondaryButton}>Edit</button>
                        {canApprove && draft.status !== "approved" ? <button type="button" onClick={() => handleStatus(draft, "approved")} disabled={busy !== ""} className={secondaryButton}>Approve</button> : null}
                        {canApprove && draft.status !== "rejected" ? <button type="button" onClick={() => handleStatus(draft, "rejected")} disabled={busy !== ""} className={secondaryButton}>Reject</button> : null}
                        {canApprove || draft.created_by_user_id === currentUserId ? <button type="button" onClick={() => handleDelete(draft)} disabled={busy !== ""} className={`${secondaryButton} text-[var(--color-danger)]`}>Delete</button> : null}
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
          {!loading && hasMore ? (
            <button type="button" onClick={handleLoadMore} disabled={busy !== ""} className={`${secondaryButton} mt-4 w-full`}>{busy === "load-more" ? "Loading…" : "Load more drafts"}</button>
          ) : null}
        </section>
      </div>
    </main>
  );
}
