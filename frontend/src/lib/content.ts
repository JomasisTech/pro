import { getApiBaseUrl } from "@/lib/auth";

export type ContentType = "general" | "promotion" | "educational" | "product" | "video_script";
export type DraftStatus = "draft" | "approved" | "rejected";

export type Draft = {
  id: string;
  content: string;
  topic: string | null;
  content_type: ContentType;
  status: DraftStatus;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type UsageMetric = { metric: string; label: string; limit: number | null; used: number; remaining: number | null };
export type Usage = { plan: string; plan_name: string; period_start: string; metrics: UsageMetric[] };

type ApiError = { detail?: string | Array<{ msg?: string }> };

const NETWORK_ERROR = "Can't reach the AutoBizPro API. Check your connection and API URL, then try again.";

function messageFrom(data: unknown, fallback: string): string {
  const detail = (data as ApiError | null)?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(" ") || fallback;
  return typeof detail === "string" && detail ? detail : fallback;
}

async function call<T>(token: string, path: string, fallback: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1${path}`, {
      ...init,
      headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(messageFrom(data, fallback));
  return data as T;
}

export const fetchUsage = (token: string, orgId: string) =>
  call<Usage>(token, `/organizations/${orgId}/usage`, "Usage could not be loaded.");

export const generateCaption = (token: string, orgId: string, topic: string, contentType: ContentType) =>
  call<{ caption: string; model: string }>(token, `/organizations/${orgId}/content/generate-caption`, "Couldn't generate a caption.", {
    method: "POST",
    body: JSON.stringify({ topic, content_type: contentType }),
  });

export type VideoPlatform = "tiktok" | "instagram_reels" | "facebook_reels" | "youtube_shorts" | "youtube_long";
export type VideoStyle = "educational" | "storytelling" | "product_demo" | "behind_the_scenes" | "testimonial_style" | "entertaining";
export const generateVideoScript = (token: string, orgId: string, payload: { topic: string; platform: VideoPlatform; duration_seconds: number; style: VideoStyle; call_to_action?: string }) =>
  call<{ script: string; model: string }>(token, `/organizations/${orgId}/content/generate-video-script`, "Couldn't generate a video script.", { method: "POST", body: JSON.stringify(payload) });

export const DRAFT_PAGE_SIZE = 50;

export const fetchDrafts = (token: string, orgId: string, offset = 0, limit = DRAFT_PAGE_SIZE) =>
  call<Draft[]>(token, `/organizations/${orgId}/drafts?limit=${limit}&offset=${offset}`, "Drafts could not be loaded.");

export const createDraft = (token: string, orgId: string, content: string, topic: string, contentType: ContentType) =>
  call<Draft>(token, `/organizations/${orgId}/drafts`, "Couldn't save the draft.", {
    method: "POST",
    body: JSON.stringify({ content, topic: topic || null, content_type: contentType }),
  });

export const updateDraft = (token: string, orgId: string, draftId: string, changes: { content?: string; status?: DraftStatus }) =>
  call<Draft>(token, `/organizations/${orgId}/drafts/${draftId}`, "Couldn't update the draft.", {
    method: "PATCH",
    body: JSON.stringify(changes),
  });

export const deleteDraft = (token: string, orgId: string, draftId: string) =>
  call<void>(token, `/organizations/${orgId}/drafts/${draftId}`, "Couldn't delete the draft.", { method: "DELETE" });
