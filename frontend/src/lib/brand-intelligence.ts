import { getApiBaseUrl } from "@/lib/auth";

export type BrandObservation = {
  id: string; social_account_id: string; provider: string; source_post_id: string; post_text: string;
  permalink: string | null; published_at: string | null; provenance: Record<string, unknown>;
};
export type BrandAnalysis = {
  id: string; status: "pending" | "approved" | "rejected"; proposal: Record<string, unknown>;
  conflicts: Array<Record<string, unknown>>; source_observation_ids: string[]; model: string | null;
  created_at: string; reviewed_at: string | null;
};
export type SocialSyncResult = {
  provider: string; retrieved: number; inserted: number; updated: number; last_synced_at: string;
  message: string;
};
export type BrandSyncJob = {
  id: string;
  social_account_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  attempts: number;
  max_attempts: number;
  result: SocialSyncResult | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  message?: string;
};

async function request<T>(token: string, orgId: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}/brand-intelligence${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) },
      cache: "no-store",
    });
  } catch {
    throw new Error("Can't reach the BizPilotPro API. Check your connection and API URL, then try again.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Brand Intelligence request failed (${response.status}).`);
  return data as T;
}

export const fetchBrandObservations = (token: string, orgId: string) => request<BrandObservation[]>(token, orgId, "/observations");
export const fetchBrandAnalyses = (token: string, orgId: string) => request<BrandAnalysis[]>(token, orgId, "/analyses");
export const syncSocialAccount = (token: string, orgId: string, accountId: string) =>
  request<SocialSyncResult>(token, orgId, `/sync/${accountId}`, { method: "POST" });
export const enqueueSocialSync = (token: string, orgId: string, accountId: string) =>
  request<BrandSyncJob>(token, orgId, `/sync-jobs/${accountId}`, { method: "POST" });
export const fetchBrandSyncJobs = (token: string, orgId: string) =>
  request<BrandSyncJob[]>(token, orgId, "/sync-jobs");
/** `ai` calls the configured model (503 without a provider); `rules` needs no AI key and never calls a model. */
export const createBrandAnalysis = (token: string, orgId: string, method: "ai" | "rules" = "ai") =>
  request<BrandAnalysis>(token, orgId, method === "rules" ? "/analyze?method=rules" : "/analyze", { method: "POST" });
export const reviewBrandAnalysis = (token: string, orgId: string, analysisId: string, decision: "approved" | "rejected") =>
  request<BrandAnalysis>(token, orgId, `/analyses/${analysisId}/review`, { method: "POST", body: JSON.stringify({ decision }) });
