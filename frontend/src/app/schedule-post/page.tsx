"use client";

import { Select } from "@/components/select";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, getStoredOrganization } from "@/lib/auth";
import { createScheduledPost, fetchApprovedContentDrafts, fetchSocialAccounts, fetchTikTokCreatorInfo, uploadScheduledVideo, type ApprovedContentDraft, type SocialAccount, type TikTokCreatorInfo, type UploadedMediaAsset } from "@/lib/social";

const field = "mt-2 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-page)] p-3 text-sm";
const MAX_VIDEO_BYTES = 1024 * 1024 * 1024;

export default function SchedulePostPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [orgId, setOrgId] = useState("");
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [approvedDrafts, setApprovedDrafts] = useState<ApprovedContentDraft[]>([]);
  const [draftId, setDraftId] = useState("");
  const [provider, setProvider] = useState<"facebook" | "tiktok">("facebook");
  const [accountId, setAccountId] = useState("");
  const [creator, setCreator] = useState<TikTokCreatorInfo | null>(null);
  const [title, setTitle] = useState("");
  const [link, setLink] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [duration, setDuration] = useState(0);
  const [privacy, setPrivacy] = useState("");
  const [allowComment, setAllowComment] = useState(false);
  const [allowDuet, setAllowDuet] = useState(false);
  const [allowStitch, setAllowStitch] = useState(false);
  const [consent, setConsent] = useState(false);
  const [uploaded, setUploaded] = useState<UploadedMediaAsset | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const availableAccounts = useMemo(() => accounts.filter((item) => item.provider === provider && item.status === "connected"), [accounts, provider]);
  const privacyOptions = creator?.privacy_level_options ?? [];
  const selectedDraft = approvedDrafts.find((draft) => draft.id === draftId);
  const content = selectedDraft?.content ?? "";
  const durationTooLong = !!creator?.max_video_post_duration_sec && duration > creator.max_video_post_duration_sec;

  useEffect(() => {
    const access = getAccessToken(); const organization = getStoredOrganization();
    if (!access || !organization) { router.replace("/login"); return; }
    setToken(access); setOrgId(organization.id);
    void Promise.all([fetchSocialAccounts(access, organization.id), fetchApprovedContentDrafts(access, organization.id)])
      .then(([items, drafts]) => { setAccounts(items); setApprovedDrafts(drafts); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load scheduling requirements."));
  }, [router]);

  useEffect(() => {
    setAccountId(availableAccounts[0]?.id ?? "");
    setCreator(null); setPrivacy("");
  }, [availableAccounts]);

  useEffect(() => {
    if (provider !== "tiktok" || !token || !orgId || !accountId) return;
    let active = true;
    void fetchTikTokCreatorInfo(token, orgId, accountId).then((value) => { if (active) setCreator(value); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Could not load TikTok creator settings."); });
    return () => { active = false; };
  }, [provider, token, orgId, accountId]);

  function selectVideo(next: File | null) {
    setFile(next); setDuration(0); setUploaded(null); setConsent(false); setError("");
    if (!next) return;
    if (next.size > MAX_VIDEO_BYTES) { setFile(null); setError("This video exceeds the 1 GiB upload limit."); return; }
    if (!["video/mp4", "video/quicktime", "video/webm"].includes(next.type)) { setFile(null); setError("Choose an MP4, MOV, or WebM video."); return; }
    const url = URL.createObjectURL(next); const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => { setDuration(Number.isFinite(video.duration) ? Math.ceil(video.duration) : 0); URL.revokeObjectURL(url); };
    video.onerror = () => { URL.revokeObjectURL(url); setError("The selected video's duration could not be read."); };
    video.src = url;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setSuccess("");
    try {
      if (!token || !orgId || !accountId) throw new Error("Choose a connected social account.");
      if (!draftId) throw new Error("Choose an approved content draft.");
      if (!approvedDrafts.some((draft) => draft.id === draftId)) throw new Error("The selected draft is no longer approved. Refresh the page and choose another.");
      if (new Date(scheduledAt).getTime() <= Date.now()) throw new Error("Choose a publishing time in the future.");
      if (provider === "tiktok") {
        if (!file || !creator || duration <= 0) throw new Error("Choose a valid video and wait for its duration and creator settings to load.");
        if (!privacy) throw new Error("Choose who can watch this video.");
        if (!consent) throw new Error("Confirm that you consent to uploading this video to TikTok.");
        if (durationTooLong) throw new Error("This video exceeds the connected TikTok account's duration limit.");
        const asset = uploaded ?? await uploadScheduledVideo(token, orgId, file);
        setUploaded(asset);
        await createScheduledPost(token, orgId, {
          draft_id: draftId, social_account_id: accountId, provider: "tiktok", title: title.trim(), content,
          media_asset_id: asset.id, video_duration_seconds: duration, privacy_level: privacy,
          allow_comment: allowComment, allow_duet: allowDuet, allow_stitch: allowStitch, consent_to_upload: consent,
          scheduled_at: new Date(scheduledAt).toISOString(),
        });
        setSuccess("TikTok video scheduled. AutoBizPro will transfer it to TikTok when the scheduled time arrives.");
        setFile(null); setUploaded(null); setDuration(0); setConsent(false); setTitle(""); setDraftId(""); setScheduledAt("");
      } else {
        await createScheduledPost(token, orgId, { draft_id: draftId, social_account_id: accountId, provider: "facebook", title: title.trim(), content,
          ...(link ? { link_url: link } : {}), scheduled_at: new Date(scheduledAt).toISOString() });
        setSuccess("Facebook post added to the publishing queue. Keep the backend dispatcher running to publish it at the selected time.");
        setTitle(""); setDraftId(""); setLink(""); setScheduledAt("");
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not schedule this post."); }
    finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-[var(--color-page)] px-4 py-8 text-[var(--color-text)]"><div className="mx-auto max-w-2xl">
    <Link href="/calendar" className="text-sm font-semibold text-[var(--color-brand)]">← Back to calendar</Link>
    <h1 className="mt-5 text-2xl font-extrabold">Schedule a social post</h1>
    <p className="mt-2 text-sm text-[var(--color-text-muted)]">Choose a connected account and schedule a Facebook text post or a TikTok video.</p>
    {error && <p role="alert" className="mt-4 rounded-xl border border-[var(--color-danger)] p-3 text-sm text-[var(--color-danger)]">{error}</p>}
    {success && <p role="status" className="mt-4 rounded-xl border border-[var(--color-success)] p-3 text-sm">{success}</p>}
    <form onSubmit={submit} className="mt-6 space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 sm:p-7">
      <label className="block text-sm font-semibold">Platform<Select value={provider} onChange={(e) => { setProvider(e.target.value as "facebook" | "tiktok"); setError(""); setSuccess(""); }} className={field}><option value="facebook">Facebook Page</option><option value="tiktok">TikTok video</option></Select></label>
      <label className="block text-sm font-semibold">{provider === "facebook" ? "Facebook Page" : "TikTok account"}<Select required value={accountId} onChange={(e) => setAccountId(e.target.value)} className={field}><option value="">Select a connected account</option>{availableAccounts.map((account) => <option key={account.id} value={account.id}>{account.account_name}</option>)}</Select></label>
      {availableAccounts.length === 0 && <p className="text-xs text-[var(--color-warning)]">No connected {provider === "facebook" ? "Facebook Page" : "TikTok account"} found. Connect one in <Link className="underline" href="/social-accounts">Social accounts</Link>.</p>}
      {provider === "tiktok" && creator && <div className="rounded-xl bg-[var(--color-page)] p-3 text-sm"><p className="font-semibold">Posting as {creator.creator_nickname || creator.creator_username || "TikTok creator"}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">Maximum video duration: {creator.max_video_post_duration_sec ?? "Unavailable"} seconds</p>{privacyOptions.length === 1 && privacyOptions[0] === "SELF_ONLY" && <p className="mt-2 text-xs font-semibold text-[var(--color-warning)]">This app is not yet audited by TikTok. Scheduled posts are restricted to Only me.</p>}</div>}
      <label className="block text-sm font-semibold">Approved content draft<Select required value={draftId} onChange={(e) => setDraftId(e.target.value)} className={field}><option value="">Select an approved draft</option>{approvedDrafts.map((draft) => <option key={draft.id} value={draft.id}>{draft.topic || draft.content.slice(0, 65)} · {draft.content_type}</option>)}</Select></label>
      {approvedDrafts.length === 0 && <p className="text-xs text-[var(--color-warning)]">There are no approved drafts available. Create a draft and have an owner or admin approve it in <Link className="underline" href="/content">Content</Link> before scheduling.</p>}
      <label className="block text-sm font-semibold">Post title<input required maxLength={300} value={title} onChange={(e) => setTitle(e.target.value)} className={field} /></label>
      <label className="block text-sm font-semibold">{provider === "tiktok" ? "TikTok caption" : "Post content"}<textarea required readOnly maxLength={provider === "tiktok" ? 2200 : 63206} rows={5} value={content} className={`${field} opacity-90`} /></label>
      {provider === "tiktok" && content.length > 2200 && <p className="text-xs text-[var(--color-danger)]">This approved draft exceeds TikTok&apos;s 2,200-character caption limit. Choose a shorter approved draft.</p>}
      {provider === "facebook" ? <label className="block text-sm font-semibold">Optional link<input type="url" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://example.com" className={field} /></label> : <>
        <label className="block text-sm font-semibold">Video file<input required type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" onChange={(e) => selectVideo(e.target.files?.[0] ?? null)} className={field} /></label>
        {file && <p className="text-xs text-[var(--color-text-muted)]">{file.name} · {(file.size / (1024 * 1024)).toFixed(1)} MB · {duration ? `${duration}s` : "Reading duration…"}{uploaded ? " · Uploaded securely" : ""}</p>}
        {durationTooLong && <p className="text-xs text-[var(--color-danger)]">This video exceeds the connected account&apos;s duration limit.</p>}
        <label className="block text-sm font-semibold">Who can watch this video?<Select required value={privacy} onChange={(e) => setPrivacy(e.target.value)} className={field}><option value="">Select privacy</option>{privacyOptions.map((option) => <option key={option} value={option}>{option === "SELF_ONLY" ? "Only me" : option === "PUBLIC_TO_EVERYONE" ? "Everyone" : option === "MUTUAL_FOLLOW_FRIENDS" ? "Friends" : option === "FOLLOWER_OF_CREATOR" ? "Followers" : option}</option>)}</Select></label>
        <div className="space-y-3"><p className="text-sm font-semibold">Allow interactions</p>{([["Comment", allowComment, setAllowComment, creator?.comment_disabled], ["Duet", allowDuet, setAllowDuet, creator?.duet_disabled], ["Stitch", allowStitch, setAllowStitch, creator?.stitch_disabled]] as const).map(([label, checked, setter, disabled]) => <label key={label} className={`flex items-center gap-3 text-sm ${disabled ? "opacity-50" : ""}`}><input type="checkbox" checked={checked} disabled={!creator || !!disabled} onChange={(e) => setter(e.target.checked)} />Allow {label}{disabled ? " (disabled in TikTok settings)" : ""}</label>)}</div>
        <label className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] p-3 text-sm"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1"/><span>I consent to storing this video in AutoBizPro and sending it to TikTok at the scheduled time.</span></label>
        <p className="text-xs text-[var(--color-text-muted)]">Your video is uploaded to private organization storage now. TikTok receives it only when the scheduled post is due.</p>
      </>}
      <label className="block text-sm font-semibold">Publish date and time<input required type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} className={field} /></label>
      <button disabled={busy || !accountId || !draftId || !content.trim() || (provider === "tiktok" && content.length > 2200) || (provider === "tiktok" && (!file || !creator || !privacy || !consent || duration <= 0 || durationTooLong))} className="w-full rounded-xl bg-[var(--color-brand)] px-4 py-3 font-bold text-white disabled:opacity-50">{busy ? (provider === "tiktok" && !uploaded ? "Uploading video…" : "Scheduling…") : "Add to publishing queue"}</button>
    </form>
  </div></main>;
}
