import { getApiBaseUrl } from "@/lib/auth";

export type ActivityEntry = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  actor_user_id: string | null;
  actor_name: string;
  created_at: string;
};

/** Filter choices for the activity page. Each maps to the API's `action_prefix` parameter. */
export const ACTIVITY_CATEGORIES: ReadonlyArray<{ value: string; label: string }> = [
  { value: "", label: "All activity" },
  { value: "auth.", label: "Registrations and sign-ins" },
  { value: "draft.", label: "Drafts" },
  { value: "content.", label: "AI generation" },
  { value: "scheduled_post.", label: "Scheduled posts" },
  { value: "facebook_post.", label: "Facebook posts" },
  { value: "tiktok_publish_job.", label: "TikTok uploads" },
  { value: "youtube_publish_job.", label: "YouTube uploads" },
  { value: "social_account.", label: "Social accounts" },
  { value: "brand_intelligence.", label: "Brand Intelligence" },
  { value: "profile.", label: "Business profile" },
  { value: "business_product.", label: "Products and services" },
  { value: "organization.", label: "Workspace and team" },
  { value: "billing.", label: "Billing" },
];

export async function fetchActivity(
  token: string, organizationId: string, limit = 50, offset = 0, actionPrefix = "",
): Promise<ActivityEntry[]> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (actionPrefix) query.set("action_prefix", actionPrefix);
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${organizationId}/activity?${query.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" && detail ? detail : "The activity log could not be loaded.");
  }
  return data as ActivityEntry[];
}
