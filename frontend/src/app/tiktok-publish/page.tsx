"use client";

import { Select } from "@/components/select";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, getStoredOrganization, type AuthOrganization } from "@/lib/auth";
import { fetchSocialAccounts, fetchTikTokCreatorInfo, fetchTikTokPublishStatus, initializeTikTokDirectPost, uploadVideoToTikTok, type SocialAccount, type TikTokCreatorInfo, type TikTokPublishStatus } from "@/lib/social";

const field = "w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-3 text-sm";
export default function TikTokPublishPage() {
  const router = useRouter();
  const [org, setOrg] = useState<AuthOrganization | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  const [creator, setCreator] = useState<TikTokCreatorInfo | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [duration, setDuration] = useState(0);
  const [caption, setCaption] = useState("");
  const [privacy, setPrivacy] = useState("");
  const [allowComment, setAllowComment] = useState(false);
  const [allowDuet, setAllowDuet] = useState(false);
  const [allowStitch, setAllowStitch] = useState(false);
  const [consent, setConsent] = useState(false);
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState<TikTokPublishStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const tiktokAccounts = useMemo(() => accounts.filter((a) => a.provider === "tiktok" && a.status === "connected"), [accounts]);
  const auditedPrivacy = creator?.privacy_level_options ?? [];

  useEffect(() => {
    const access = getAccessToken(); const active = getStoredOrganization();
    if (!access || !active) { router.replace("/login"); return; }
    setOrg(active); setToken(access);
    void fetchSocialAccounts(access, active.id).then((rows) => { const found = rows.filter((a) => a.provider === "tiktok" && a.status === "connected"); setAccounts(rows); if (found[0]) setAccountId(found[0].id); }).catch((e) => setError(e instanceof Error ? e.message : "Could not load TikTok accounts."));
  }, [router]);

  useEffect(() => {
    if (!token || !org || !accountId) { setCreator(null); return; }
    setError(""); setPrivacy(""); setConsent(false); setAllowComment(false); setAllowDuet(false); setAllowStitch(false);
    void fetchTikTokCreatorInfo(token, org.id, accountId).then(setCreator).catch((e) => setError(e instanceof Error ? e.message : "Could not load creator settings."));
  }, [token, org, accountId]);

  useEffect(() => {
    if (!token || !org || !jobId || status?.published || status?.status === "failed" || status?.status === "sent_to_inbox") return;
    const timer = window.setInterval(() => {
      void fetchTikTokPublishStatus(token, org.id, jobId).then((next) => {
        setStatus(next);
        if (next.published) setMessage("TikTok confirmed that your video was published.");
        else if (next.status === "failed") setMessage("TikTok reported that publishing failed.");
        else setMessage("TikTok is processing your video. This page will keep checking automatically.");
      }).catch(() => { /* A temporary status-check failure is retried on the next interval. */ });
    }, 10000);
    return () => window.clearInterval(timer);
  }, [token, org, jobId, status?.published, status?.status]);

  function chooseFile(next: File | null) {
    setFile(next); setDuration(0); setStatus(null); setJobId(""); setError("");
    if (!next) return;
    const url = URL.createObjectURL(next); const video = document.createElement("video"); video.preload = "metadata"; video.onloadedmetadata = () => { setDuration(Number.isFinite(video.duration) ? Math.ceil(video.duration) : 0); URL.revokeObjectURL(url); }; video.onerror = () => { URL.revokeObjectURL(url); setError("The selected video metadata could not be read."); }; video.src = url;
  }

  async function publish() {
    if (!token || !org || !accountId || !file || !creator || !privacy || !consent || duration <= 0) return;
    setBusy(true); setError(""); setMessage("Preparing your TikTok upload…");
    try {
      const initialized = await initializeTikTokDirectPost(token, org.id, accountId, {
        video_size: file.size, duration_seconds: duration, caption, privacy_level: privacy,
        allow_comment: allowComment, allow_duet: allowDuet, allow_stitch: allowStitch, consent_to_upload: consent,
      });
      setJobId(initialized.job_id);
      setMessage("Uploading video to TikTok. Keep this page open until the upload finishes…");
      await uploadVideoToTikTok(initialized.upload_url, file, initialized.chunk_size);
      setMessage("Video uploaded to TikTok. AutoBizPro will check the publishing status automatically.");
    } catch (e) { setError(e instanceof Error ? e.message : "TikTok publishing could not be started."); setMessage(""); }
    finally { setBusy(false); }
  }

  async function checkStatus() {
    if (!token || !org || !jobId) return;
    setBusy(true); setError("");
    try { const next = await fetchTikTokPublishStatus(token, org.id, jobId); setStatus(next); setMessage(next.published ? "TikTok confirmed that your video was published." : next.status === "failed" ? "TikTok reported that publishing failed." : "TikTok is still processing your video. It may take a few minutes."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not check TikTok status."); }
    finally { setBusy(false); }
  }

  const privateOnly = !!creator && auditedPrivacy.length > 0 && auditedPrivacy.every((p) => p === "SELF_ONLY");
  const durationTooLong = !!creator?.max_video_post_duration_sec && duration > creator.max_video_post_duration_sec;
  const canPublish = !!file && duration > 0 && !!creator && !!privacy && !!consent && !durationTooLong && !busy && !jobId;

  return <main className="min-h-screen bg-[var(--color-page)] px-4 py-8 text-[var(--color-text)] sm:px-6"><div className="mx-auto max-w-3xl">
    <Link href="/social-accounts" className="text-sm font-semibold text-[var(--color-brand)]">← Social accounts</Link>
    <header className="mt-5"><p className="text-xs font-bold tracking-widest text-[var(--color-brand)]">CONTENT STUDIO</p><h1 className="mt-2 text-3xl font-extrabold">Publish a TikTok video</h1><p className="mt-2 text-sm text-[var(--color-text-muted)]">Choose a connected account, review its current posting settings, then upload your video directly to TikTok.</p></header>
    {error && <p role="alert" className="mt-5 rounded-xl border border-[var(--color-danger)]/30 p-3 text-sm text-[var(--color-danger)]">{error}</p>}
    {message && <p role="status" className="mt-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm">{message}</p>}
    <section className="mt-6 space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 sm:p-7">
      <div><label className="mb-2 block text-sm font-semibold">TikTok account</label><Select className={field} value={accountId} onChange={(e) => { setAccountId(e.target.value); setJobId(""); setStatus(null); }}><option value="">Choose an account</option>{tiktokAccounts.map((a) => <option key={a.id} value={a.id}>{a.account_name}</option>)}</Select>{tiktokAccounts.length === 0 && <p className="mt-2 text-xs text-[var(--color-text-muted)]">Connect a TikTok account first.</p>}</div>
      {creator && <div className="rounded-xl bg-[var(--color-page)] p-3 text-sm"><p className="font-semibold">Posting as {creator.creator_nickname || creator.creator_username || "TikTok creator"}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">Maximum video duration: {creator.max_video_post_duration_sec ?? "Unavailable"} seconds</p>{privateOnly && <p className="mt-2 text-xs font-semibold">This app is not yet audited by TikTok. Posts are restricted to Only me.</p>}</div>}
      <div><label className="mb-2 block text-sm font-semibold">Video file</label><input className={field} type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm" onChange={(e) => chooseFile(e.target.files?.[0] ?? null)} />{file && <p className="mt-2 text-xs text-[var(--color-text-muted)]">{file.name} · {(file.size / (1024 * 1024)).toFixed(1)} MB · {duration ? `${duration}s` : "Reading duration…"}</p>}{durationTooLong && <p className="mt-2 text-xs text-[var(--color-danger)]">This video exceeds the connected account’s duration limit.</p>}</div>
      <div><label className="mb-2 block text-sm font-semibold">Caption</label><textarea className={field} rows={4} maxLength={2200} value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Write your TikTok caption…"/><p className="mt-1 text-right text-xs text-[var(--color-text-muted)]">{caption.length}/2200</p></div>
      <div><label className="mb-2 block text-sm font-semibold">Who can watch this video?</label><Select className={field} value={privacy} onChange={(e) => setPrivacy(e.target.value)}><option value="">Select privacy (required)</option>{auditedPrivacy.map((p) => <option key={p} value={p}>{p === "SELF_ONLY" ? "Only me" : p === "PUBLIC_TO_EVERYONE" ? "Everyone" : p === "MUTUAL_FOLLOW_FRIENDS" ? "Friends" : "Followers"}</option>)}</Select></div>
      <div className="space-y-3"><p className="text-sm font-semibold">Allow interactions (all off by default)</p>{([ ["Comment", allowComment, setAllowComment, creator?.comment_disabled], ["Duet", allowDuet, setAllowDuet, creator?.duet_disabled], ["Stitch", allowStitch, setAllowStitch, creator?.stitch_disabled] ] as const).map(([label, checked, setter, disabled]) => <label key={label} className={`flex items-center gap-3 text-sm ${disabled ? "opacity-50" : ""}`}><input type="checkbox" checked={checked} disabled={!creator || !!disabled} onChange={(e) => setter(e.target.checked)} />Allow {label}{disabled ? " (disabled in TikTok settings)" : ""}</label>)}</div>
      <label className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] p-3 text-sm"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1"/><span>I consent to sending this video and caption to TikTok for upload and publishing. I understand TikTok may take a few minutes to process it.</span></label>
      <button type="button" disabled={!canPublish} onClick={() => void publish()} className="w-full rounded-xl bg-[var(--color-brand)] px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Working…" : "Upload and publish to TikTok"}</button>
    </section>
    {jobId && <section className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 sm:p-7"><h2 className="font-bold">Publishing status</h2><p className="mt-2 text-sm text-[var(--color-text-muted)]">Your video has been sent to TikTok. A successful upload is not the same as a completed post; status checks run automatically.</p><button type="button" disabled={busy} onClick={() => void checkStatus()} className="mt-4 rounded-xl border border-[var(--color-border)] px-4 py-3 text-sm font-semibold">{busy ? "Checking…" : "Check TikTok status"}</button>{status && <p className="mt-3 text-sm">Status: <strong>{status.status.replaceAll("_", " ")}</strong>{status.failure_reason ? ` · ${status.failure_reason}` : ""}</p>}</section>}
    <p className="mt-5 text-xs leading-5 text-[var(--color-text-muted)]">TikTok approval is required for public publishing. Before approval, this integration restricts the privacy selection to Only me. The video is uploaded directly from your browser to TikTok; AutoBizPro does not store the video file or expose your TikTok access token.</p>
  </div></main>;
}
