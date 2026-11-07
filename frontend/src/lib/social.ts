import { getApiBaseUrl } from "@/lib/auth";

export type SocialProvider = { key: string; name: string; description: string; connection_available: boolean };
export type SocialAccount = {
  id: string; provider: string; provider_account_id: string; account_name: string;
  account_type: string | null; status: string; granted_scopes: string[];
  connected_at: string; last_synced_at: string | null; token_expires_at: string | null;
};

async function request<T>(token: string, orgId: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/social-accounts${path}`, {
      ...init, headers: { Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) }, cache: "no-store",
    });
  } catch { throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again."); }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Social accounts request failed (${response.status}).`);
  return data as T;
}
export const fetchSocialProviders = (token: string, orgId: string) => request<SocialProvider[]>(token, orgId, "/providers");
export const fetchSocialAccounts = (token: string, orgId: string) => request<SocialAccount[]>(token, orgId, "");
export const disconnectSocialAccount = (token: string, orgId: string, accountId: string) => request<void>(token, orgId, `/${accountId}`, { method: "DELETE" });

export async function startInstagramConnection(token: string, orgId: string): Promise<string> {
  const result = await request<{ authorization_url: string }>(token, orgId, "/instagram/connect", { method: "POST" });
  return result.authorization_url;
}

export async function startYouTubeConnection(token: string, orgId: string): Promise<string> {
  const result = await request<{ authorization_url: string }>(token, orgId, "/youtube/connect", { method: "POST" });
  return result.authorization_url;
}

export async function startTikTokConnection(token: string, orgId: string): Promise<string> {
  const result = await request<{ authorization_url: string }>(token, orgId, "/tiktok/connect", { method: "POST" });
  return result.authorization_url;
}

export type TikTokCreatorInfo = {
  creator_username: string | null; creator_nickname: string | null; privacy_level_options: string[];
  comment_disabled: boolean; duet_disabled: boolean; stitch_disabled: boolean; max_video_post_duration_sec: number | null;
};
export type TikTokPublishInit = { job_id: string; publish_id: string; upload_url: string; chunk_size: number; total_chunk_count: number; upload_method: "PUT"; message: string };
export type TikTokPublishStatus = { job_id: string; status: string; provider_status: string; failure_reason: string | null; published: boolean };

async function tiktokRequest<T>(token: string, orgId: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/tiktok${path}`, {
      ...init, headers: { Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) }, cache: "no-store",
    });
  } catch { throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `TikTok publishing request failed (${response.status}).`);
  return data as T;
}
export const fetchTikTokCreatorInfo = (token: string, orgId: string, accountId: string) =>
  tiktokRequest<TikTokCreatorInfo>(token, orgId, `/accounts/${accountId}/creator-info`);
export const initializeTikTokDirectPost = (token: string, orgId: string, accountId: string, payload: {
  video_size: number; duration_seconds: number; caption: string; privacy_level: string;
  allow_comment: boolean; allow_duet: boolean; allow_stitch: boolean; consent_to_upload: boolean;
}) => tiktokRequest<TikTokPublishInit>(token, orgId, `/accounts/${accountId}/direct-post`, { method: "POST", body: JSON.stringify(payload) });
export const fetchTikTokPublishStatus = (token: string, orgId: string, jobId: string) =>
  tiktokRequest<TikTokPublishStatus>(token, orgId, `/publish-jobs/${jobId}`);

export async function uploadVideoToTikTok(uploadUrl: string, file: File, chunkSize: number): Promise<void> {
  const mime = file.type || "video/mp4";
  if (!["video/mp4", "video/quicktime", "video/webm"].includes(mime)) throw new Error("Choose an MP4, MOV or WebM video file.");
  for (let start = 0; start < file.size; start += chunkSize) {
    const endExclusive = Math.min(start + chunkSize, file.size);
    const chunk = file.slice(start, endExclusive);
    const response = await fetch(uploadUrl, {
      method: "PUT", headers: { "Content-Type": mime, "Content-Range": `bytes ${start}-${endExclusive - 1}/${file.size}` }, body: chunk,
    });
    if (!response.ok) throw new Error(`TikTok video upload failed at byte ${start} (${response.status}). You can retry by starting a new upload.`);
  }
}

export type YouTubeUploadInit = { job_id: string; upload_url: string; video_size: number; chunk_size: number; status: string; message: string };
export type YouTubePublishStatus = { job_id: string; status: string; video_id: string | null; privacy_status?: string | null; upload_status?: string; processing_status?: string | null; failure_reason?: string | null; video_url?: string | null; message?: string };
async function youtubeRequest<T>(token: string, orgId: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/youtube${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) }, cache: "no-store" }); }
  catch { throw new Error("Can't reach the AutoBizPro API. Check your connection and try again."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `YouTube request failed (${response.status}).`);
  return data as T;
}
export const initializeYouTubeUpload = (token: string, orgId: string, accountId: string, payload: { video_size: number; mime_type: string; title: string; description: string; tags: string[]; privacy_status: string; made_for_kids: boolean; consent_to_upload: boolean }) =>
  youtubeRequest<YouTubeUploadInit>(token, orgId, `/accounts/${accountId}/upload`, { method: "POST", body: JSON.stringify(payload) });
export const completeYouTubeUpload = (token: string, orgId: string, jobId: string, videoId: string) =>
  youtubeRequest<{ job_id: string; video_id: string; status: string; message: string }>(token, orgId, `/publish-jobs/${jobId}/complete`, { method: "POST", body: JSON.stringify({ video_id: videoId }) });
export const fetchYouTubePublishStatus = (token: string, orgId: string, jobId: string) =>
  youtubeRequest<YouTubePublishStatus>(token, orgId, `/publish-jobs/${jobId}`);

export async function uploadVideoToYouTube(uploadUrl: string, file: File, chunkSize: number, onProgress: (percent: number) => void): Promise<string> {
  let offset = 0; let retries = 0;
  const mime = file.type || "video/mp4";
  while (offset < file.size) {
    const end = Math.min(offset + chunkSize, file.size);
    try {
      const response = await fetch(uploadUrl, { method: "PUT", headers: { "Content-Type": mime, "Content-Range": `bytes ${offset}-${end - 1}/${file.size}` }, body: file.slice(offset, end) });
      if (response.status === 200 || response.status === 201) {
        const body = await response.json(); if (!body.id) throw new Error("YouTube completed the upload without returning a video ID.");
        onProgress(100); return String(body.id);
      }
      if (response.status === 308) {
        const range = response.headers.get("Range");
        offset = range ? Number(range.split("-").at(-1)) + 1 : 0;
        retries = 0; onProgress(Math.floor((offset / file.size) * 100)); continue;
      }
      if (response.status >= 500 || response.status === 429) throw new Error("temporary");
      throw new Error(`YouTube rejected the upload (${response.status}).`);
    } catch (error) {
      if (error instanceof Error && error.message !== "temporary" && !error.message.includes("fetch")) throw error;
      retries += 1; if (retries > 5) throw new Error("Upload paused after repeated network failures. You can retry from this page while the resumable session remains valid.");
      await new Promise((resolve) => setTimeout(resolve, Math.min(1000 * 2 ** retries, 15000)));
      const probe = await fetch(uploadUrl, { method: "PUT", headers: { "Content-Range": `bytes */${file.size}` } });
      if (probe.status === 200 || probe.status === 201) { const body = await probe.json(); if (body.id) { onProgress(100); return String(body.id); } }
      if (probe.status === 308) { const range = probe.headers.get("Range"); offset = range ? Number(range.split("-").at(-1)) + 1 : 0; onProgress(Math.floor((offset / file.size) * 100)); }
      else if (!probe.ok) throw new Error(`Could not resume YouTube upload (${probe.status}).`);
    }
  }
  throw new Error("YouTube upload ended without a confirmed video ID.");
}

export async function startFacebookConnection(token: string, orgId: string): Promise<string> {
  const result = await request<{ authorization_url: string }>(token, orgId, "/facebook/connect", { method: "POST" });
  return result.authorization_url;
}

export type CalendarItem = { id: string; kind: string; platform: string; title: string; content: string; status: string; created_at: string; scheduled_at: string | null; external_post_id?: string | null };
export async function publishFacebookPost(token: string, orgId: string, payload: { social_account_id: string; message: string; link?: string; scheduled_at?: string }) {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/facebook/publish`, { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify(payload), cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Facebook publishing failed (${response.status}).`);
  return data as { provider: string; account_name: string; post_id: string; status: string; scheduled_at: string | null };
}
export async function fetchCalendar(token: string, orgId: string): Promise<CalendarItem[]> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/calendar`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Calendar request failed (${response.status}).`);
  return data as CalendarItem[];
}

export type ApprovedContentDraft = { id: string; content: string; topic: string | null; content_type: string; status: "approved" };
export async function fetchApprovedContentDrafts(token: string, orgId: string): Promise<ApprovedContentDraft[]> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/drafts?status=approved&limit=100`, {
    headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Approved drafts request failed (${response.status}).`);
  return data as ApprovedContentDraft[];
}

export type ScheduledPost = {
  id: string; draft_id: string | null; social_account_id: string; provider: string; title: string; content: string;
  link_url: string | null; scheduled_at: string; status: string; attempts: number;
  external_post_id: string | null; last_error: string | null; created_at: string; updated_at: string;
};
async function schedulingRequest<T>(token: string, orgId: string, path = "", init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/scheduled-posts${path}`, {
    ...init, headers: { Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) }, cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Scheduling request failed (${response.status}).`);
  return data as T;
}
export const createScheduledPost = (token: string, orgId: string, payload: {
  draft_id: string; social_account_id: string; provider: "facebook" | "tiktok"; title: string; content: string;
  link_url?: string; media_asset_id?: string; video_duration_seconds?: number; privacy_level?: string;
  allow_comment?: boolean; allow_duet?: boolean; allow_stitch?: boolean; consent_to_upload?: boolean; scheduled_at: string;
}) => schedulingRequest<ScheduledPost>(token, orgId, "", { method: "POST", body: JSON.stringify(payload) });

export type UploadedMediaAsset = {
  id: string; filename: string; content_type: string; size_bytes: number; sha256: string;
  status: string; delivery_configured: boolean;
};
export async function uploadScheduledVideo(token: string, orgId: string, file: File): Promise<UploadedMediaAsset> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/media-assets`, {
      method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": file.type || "video/mp4", "X-File-Name": encodeURIComponent(file.name) },
      body: file, cache: "no-store",
    });
  } catch { throw new Error("Can't reach the AutoBizPro API while uploading your video."); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Video upload failed (${response.status}).`);
  return data as UploadedMediaAsset;
}

export const fetchScheduledPosts = (token: string, orgId: string) => schedulingRequest<ScheduledPost[]>(token, orgId);
export const cancelScheduledPost = (token: string, orgId: string, id: string) => schedulingRequest<void>(token, orgId, `/${id}`, { method: "DELETE" });
export const reschedulePost = (token: string, orgId: string, id: string, scheduled_at: string) =>
  schedulingRequest<ScheduledPost>(token, orgId, `/${id}/reschedule`, { method: "PATCH", body: JSON.stringify({ scheduled_at }) });
