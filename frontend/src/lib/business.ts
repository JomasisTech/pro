import { getApiBaseUrl } from "@/lib/auth";

export type BusinessProduct = {
  id: string; name: string; description: string | null; price_amount: number | null;
  price_currency: string | null; is_primary: boolean; is_active: boolean;
  created_at: string; updated_at: string;
};
export type ProfileVersion = {
  version_number: number; action: string; snapshot: Record<string, unknown>;
  changed_by_user_id: string | null; created_at: string;
};
export type ProfileConfirmation = {
  organization_id: string; profile_version: number; confirmed_at: string;
  onboarding_completed_at: string; message: string;
};

type ApiError = { detail?: string | Array<{ msg?: string }> };
function apiMessage(data: unknown, fallback: string) {
  const detail = (data as ApiError | null)?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(" ") || fallback;
  return typeof detail === "string" ? detail : fallback;
}
async function request<T>(token: string, orgId: string, path: string, fallback: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/organizations/${orgId}${path}`, {
      ...init, headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), Authorization: `Bearer ${token}` }, cache: "no-store",
    });
  } catch { throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again."); }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(apiMessage(data, `${fallback} (${response.status})`));
  return data as T;
}
export const fetchProducts = (token: string, orgId: string) => request<BusinessProduct[]>(token, orgId, "/products", "Products could not be loaded.");
export const createProduct = (token: string, orgId: string, payload: Pick<BusinessProduct, "name" | "description" | "price_amount" | "price_currency" | "is_primary">) => request<BusinessProduct>(token, orgId, "/products", "Product could not be created.", { method: "POST", body: JSON.stringify(payload) });
export const updateProduct = (token: string, orgId: string, id: string, payload: Partial<Pick<BusinessProduct, "name" | "description" | "price_amount" | "price_currency" | "is_primary" | "is_active">>) => request<BusinessProduct>(token, orgId, `/products/${id}`, "Product could not be updated.", { method: "PATCH", body: JSON.stringify(payload) });
export const deleteProduct = (token: string, orgId: string, id: string) => request<void>(token, orgId, `/products/${id}`, "Product could not be deleted.", { method: "DELETE" });
export const confirmBusinessProfile = (token: string, orgId: string) => request<ProfileConfirmation>(token, orgId, "/profile/confirm", "Profile could not be confirmed.", { method: "POST" });
export const fetchProfileVersions = (token: string, orgId: string) => request<ProfileVersion[]>(token, orgId, "/profile/versions", "Profile history could not be loaded.");
