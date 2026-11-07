import { getApiBaseUrl } from "@/lib/auth";

export type Category = {
  id: string;
  slug: string;
  name: string;
  subcategories: Category[];
};

export type BusinessProfileInput = {
  business_name: string;
  industry_id: string | null;
  niche: string | null;
  subcategory_id: string | null;
  description: string | null;
  products_services: string | null;
  location: string | null;
  target_audience: string | null;
  audience_type: "consumers" | "businesses" | "both" | null;
  geographic_market: string | null;
  unique_selling_points: string | null;
  brand_voice: string | null;
  preferred_tone: string | null;
  preferred_words: string | null;
  avoided_words: string | null;
  brand_voice_mode: "automatic" | "manual" | "hybrid";
  custom_ai_instructions: string | null;
  language: string;
  marketing_goals: string | null;
  posting_frequency: string | null;
};

export type BusinessProfile = BusinessProfileInput & { organization_id: string; updated_at: string; profile_version: number; confirmed_at: string | null; onboarding_completed_at: string | null };

type ApiError = { detail?: string | Array<{ msg?: string }> };

const NETWORK_ERROR = "Can't reach the AutoBizPro API. Check your connection and API URL, then try again.";

function messageFrom(data: unknown, fallback: string): string {
  const detail = (data as ApiError | null)?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(" ") || fallback;
  return typeof detail === "string" && detail ? detail : fallback;
}

async function send(path: string, token: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${getApiBaseUrl()}/api/v1${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }
}

export async function fetchCategories(token: string): Promise<Category[]> {
  const response = await send("/categories", token);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(messageFrom(data, "Industries could not be loaded."));
  return data as Category[];
}

/** Returns null when the organization has not saved a profile yet (the API answers 404). */
export async function fetchBusinessProfile(token: string, organizationId: string): Promise<BusinessProfile | null> {
  const response = await send(`/organizations/${organizationId}/profile`, token);
  if (response.status === 404) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(messageFrom(data, "The business profile could not be loaded."));
  return data as BusinessProfile;
}

export async function saveBusinessProfile(
  token: string,
  organizationId: string,
  profile: BusinessProfileInput,
): Promise<BusinessProfile> {
  const response = await send(`/organizations/${organizationId}/profile`, token, {
    method: "PUT",
    body: JSON.stringify(profile),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(messageFrom(data, `Couldn't save the profile (${response.status}). Try again.`));
  return data as BusinessProfile;
}

const skipKey = (organizationId: string) => `autobizpro-onboarding-skipped:${organizationId}`;

/** "Skip for now" lasts for the browser session so the dashboard doesn't keep redirecting. */
export function skipOnboarding(organizationId: string) {
  try {
    window.sessionStorage.setItem(skipKey(organizationId), "1");
  } catch {
    // Storage can be unavailable (private mode); the user will simply be asked again.
  }
}

export function onboardingSkipped(organizationId: string): boolean {
  try {
    return window.sessionStorage.getItem(skipKey(organizationId)) === "1";
  } catch {
    return false;
  }
}
