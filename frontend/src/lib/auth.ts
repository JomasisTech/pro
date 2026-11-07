const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export type AuthUser = {
  id: string;
  /** Null for accounts created with WhatsApp. */
  email: string | null;
  full_name: string;
  is_active: boolean;
  /** False for accounts that sign in with Google or WhatsApp and have no password of their own. */
  has_password: boolean;
  email_verified_at: string | null;
  created_at: string;
};

/** The name given to WhatsApp accounts until the person tells us theirs. */
export const PLACEHOLDER_ACCOUNT_NAME = "WhatsApp user";

/** True when the account still has the placeholder name, so the interface should not greet them by it. */
export function hasPlaceholderName(user: AuthUser | null): boolean {
  return !user || !user.full_name.trim() || user.full_name === PLACEHOLDER_ACCOUNT_NAME;
}

/** Workspaces created by Google/WhatsApp sign-in get a generic name ("Ada's Workspace", "My Workspace"). */
export function isPlaceholderWorkspaceName(name: string): boolean {
  return name === "My Workspace" || /'s Workspace$/.test(name);
}

export type AuthProviders = { google: boolean; whatsapp: boolean };

export type AuthOrganization = {
  id: string;
  name: string;
  slug: string;
  role: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
  organization: AuthOrganization;
};

type ApiError = { detail?: string | Array<{ msg?: string }> };

async function requestAuth(path: string, payload: Record<string, string>): Promise<AuthResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again.");
  }

  const data = (await response.json().catch(() => ({}))) as AuthResponse | ApiError;
  if (!response.ok) {
    const detail = (data as ApiError).detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).filter(Boolean).join(" ")
      : detail;
    throw new Error(message || `Request failed (${response.status}). Please try again.`);
  }
  return data as AuthResponse;
}

export function registerAccount(payload: {
  email: string;
  password: string;
  full_name: string;
  organization_name: string;
}) {
  return requestAuth("register", payload);
}

export function loginAccount(payload: { email: string; password: string; totp_code?: string }) {
  return requestAuth("login", payload);
}

/** Creates a platform-owner session only when the backend explicitly enables DEMO_MODE. */
export async function loginDemoPlatformAdmin(): Promise<AuthResponse> {
  return requestAuth("demo-admin", {});
}

export type DemoInfo = { enabled: false } | { enabled: true; email: string; password: string };

/** Asks the API whether demo mode is on (only ever true on a local/demo server). */
export async function fetchDemoInfo(): Promise<DemoInfo> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/demo`, { cache: "no-store" });
    if (!response.ok) return { enabled: false };
    const data = (await response.json()) as { enabled?: boolean; email?: string; password?: string };
    return data.enabled === true && data.email && data.password
      ? { enabled: true, email: data.email, password: data.password }
      : { enabled: false };
  } catch {
    return { enabled: false };
  }
}

/** Which social sign-in options this deployment has set up. Falls back to "none" so no broken button is shown. */
export async function fetchAuthProviders(): Promise<AuthProviders> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/providers`, { cache: "no-store" });
    if (!response.ok) return { google: false, whatsapp: false };
    const data = (await response.json()) as Partial<AuthProviders>;
    return { google: data.google === true, whatsapp: data.whatsapp === true };
  } catch {
    return { google: false, whatsapp: false };
  }
}


/** Consume a one-time email verification link. */
export async function verifyEmail(token: string): Promise<string> {
  const result = await postJson<{ message: string }>("verify-email", { token });
  return result.message;
}

/** Request a replacement verification link; server response does not reveal account existence. */
export async function resendVerification(email: string): Promise<string> {
  const result = await postJson<{ message: string }>("resend-verification", { email });
  return result.message;
}

/** Ask the server to send a one-time sign-in code to this WhatsApp number. */
export async function requestWhatsAppCode(phone: string): Promise<string> {
  const result = await postJson<{ message: string }>("whatsapp/request-code", { phone });
  return result.message;
}

/** Check the code. Signs in (or creates) the account for this number. */
export function verifyWhatsAppCode(phone: string, code: string, fullName?: string) {
  return postJson<AuthResponse>("whatsapp/verify", { phone, code, ...(fullName ? { full_name: fullName } : {}) });
}

export function saveAuthSession(result: AuthResponse) {
  // Transitional MVP session. Before production, review an HttpOnly Secure cookie flow.
  window.sessionStorage.setItem("autobizpro-access-token", result.access_token);
  window.sessionStorage.setItem("autobizpro-user", JSON.stringify(result.user));
  window.sessionStorage.setItem("autobizpro-organization", JSON.stringify(result.organization));
}

export function getAccessToken() {
  return window.sessionStorage.getItem("autobizpro-access-token");
}

export function getStoredUserId(): string | null {
  const raw = window.sessionStorage.getItem("autobizpro-user");
  if (!raw) return null;
  try {
    return (JSON.parse(raw) as AuthUser).id;
  } catch {
    return null;
  }
}

export function getStoredUser(): AuthUser | null {
  const raw = window.sessionStorage.getItem("autobizpro-user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function getStoredOrganization(): AuthOrganization | null {
  const raw = window.sessionStorage.getItem("autobizpro-organization");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthOrganization;
  } catch {
    window.sessionStorage.removeItem("autobizpro-organization");
    return null;
  }
}

export async function fetchCurrentUser(token: string): Promise<AuthUser> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again.");
  }

  const data = (await response.json().catch(() => ({}))) as AuthUser | ApiError;
  if (!response.ok) {
    const detail = (data as ApiError).detail;
    throw new Error(typeof detail === "string" ? detail : "Your session is no longer valid.");
  }
  return data as AuthUser;
}

export async function fetchMyOrganizations(token: string): Promise<AuthOrganization[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/organizations`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again.");
  }

  const data = (await response.json().catch(() => ({}))) as AuthOrganization[] | ApiError;
  if (!response.ok) {
    const detail = (data as ApiError).detail;
    throw new Error(typeof detail === "string" ? detail : "Your workspaces could not be loaded.");
  }
  return data as AuthOrganization[];
}

export async function createOrganization(token: string, name: string): Promise<AuthOrganization> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/organizations`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name }),
    });
  } catch {
    throw new Error("Can't reach the AutoBizPro API. Check your connection and API URL, then try again.");
  }

  const data = (await response.json().catch(() => ({}))) as AuthOrganization | ApiError;
  if (!response.ok) {
    const detail = (data as ApiError).detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).filter(Boolean).join(" ")
      : detail;
    throw new Error(message || `Couldn't create the workspace (${response.status}). Try again.`);
  }
  return data as AuthOrganization;
}

export function saveActiveOrganization(organization: AuthOrganization) {
  window.sessionStorage.setItem("autobizpro-organization", JSON.stringify(organization));
}

const NETWORK_ERROR = "Can't reach the AutoBizPro API. Check your connection and API URL, then try again.";

function errorText(data: unknown, status: number, fallback: string): string {
  const detail = (data as ApiError | undefined)?.detail;
  const message = Array.isArray(detail) ? detail.map((item) => item.msg).filter(Boolean).join(" ") : detail;
  return message || `${fallback} (${status}).`;
}

async function postJson<T>(path: string, body: Record<string, string> | null, token?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }
  const data = (await response.json().catch(() => ({}))) as unknown;
  if (!response.ok) throw new Error(errorText(data, response.status, "Request failed"));
  return data as T;
}

/** Ask the server to revoke this session's token. Best effort: local sign-out must always succeed. */
export async function logoutAccount(token: string | null): Promise<void> {
  if (!token) return;
  try {
    await postJson<{ message: string }>("logout", null, token);
  } catch {
    // Offline, or the token was already invalid/expired; either way the local session is cleared next.
  }
}

/** Revoke every session of this account on every device. */
export function logoutEverywhere(token: string) {
  return postJson<{ message: string }>("logout-all", null, token);
}

/** Change the password; the response carries a fresh session token because older tokens stop working. */
export function changePassword(token: string, currentPassword: string, newPassword: string) {
  return postJson<AuthResponse>("change-password", { current_password: currentPassword, new_password: newPassword }, token);
}

export async function requestPasswordReset(email: string): Promise<string> {
  const result = await postJson<{ message: string }>("forgot-password", { email });
  return result.message;
}

export async function resetPassword(token: string, newPassword: string): Promise<string> {
  const result = await postJson<{ message: string }>("reset-password", { token, new_password: newPassword });
  return result.message;
}

async function sendJson<T>(method: "PATCH" | "DELETE", path: string, token: string, body: Record<string, string> | null): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/${path}`, {
      method,
      headers: { ...(body ? { "Content-Type": "application/json" } : {}), Authorization: `Bearer ${token}` },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }
  if (response.status === 204) return undefined as T;
  const data = (await response.json().catch(() => ({}))) as unknown;
  if (!response.ok) throw new Error(errorText(data, response.status, "Request failed"));
  return data as T;
}

/** Update the signed-in user's display name and refresh the stored copy. */
export async function updateAccountName(token: string, fullName: string): Promise<AuthUser> {
  const user = await sendJson<AuthUser>("PATCH", "auth/me", token, { full_name: fullName });
  window.sessionStorage.setItem("autobizpro-user", JSON.stringify(user));
  return user;
}

export function renameWorkspace(token: string, organizationId: string, name: string) {
  return sendJson<AuthOrganization>("PATCH", `organizations/${organizationId}`, token, { name });
}

/** Permanently delete a workspace; `confirmName` must equal its current name. */
export function deleteWorkspace(token: string, organizationId: string, confirmName: string) {
  return sendJson<void>("DELETE", `organizations/${organizationId}?confirm_name=${encodeURIComponent(confirmName)}`, token, null);
}

/** Sign out on the server (revoking the token), then clear this browser's session. */
export async function signOutAccount() {
  await logoutAccount(getAccessToken());
  clearAuthSession();
}

export function clearAuthSession() {
  window.sessionStorage.removeItem("autobizpro-access-token");
  window.sessionStorage.removeItem("autobizpro-user");
  window.sessionStorage.removeItem("autobizpro-organization");
}

export function getApiBaseUrl() {
  return API_BASE_URL;
}

/** Accept a workspace invitation using the currently authenticated account. */
export async function acceptOrganizationInvitation(token: string, accessToken: string): Promise<AuthOrganization> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/organizations/invitations/accept`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ token }),
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }
  const data = (await response.json().catch(() => ({}))) as AuthOrganization | ApiError;
  if (!response.ok) throw new Error(errorText(data, response.status, "Invitation could not be accepted"));
  return data as AuthOrganization;
}

export type WorkspaceInvitation = {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  accepted_at: string | null;
  last_sent_at?: string | null;
  status?: "pending" | "accepted" | "expired";
  created_at: string;
};

async function organizationRequest<T>(token: string, path: string, method = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new Error(NETWORK_ERROR);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorText(data, response.status, "Workspace request failed"));
  return data as T;
}

export function listWorkspaceInvitations(token: string, organizationId: string) {
  return organizationRequest<WorkspaceInvitation[]>(token, `organizations/${organizationId}/invitations`);
}

export function inviteWorkspaceMember(token: string, organizationId: string, email: string, role: "admin" | "member") {
  return organizationRequest<{ email: string; role: string; expires_at: string; message: string }>(
    token, `organizations/${organizationId}/invitations`, "POST", { email, role },
  );
}

/** Issue a fresh link (earlier links stop working). Refused for 60 seconds after the previous send. */
export function resendWorkspaceInvitation(token: string, organizationId: string, invitationId: string) {
  return organizationRequest<{ message: string }>(token, `organizations/${organizationId}/invitations/${invitationId}/resend`, "POST", {});
}

export function revokeWorkspaceInvitation(token: string, organizationId: string, invitationId: string) {
  return organizationRequest<void>(token, `organizations/${organizationId}/invitations/${invitationId}`, "DELETE");
}

export type WorkspaceMember = { user_id: string; email: string | null; full_name: string; role: "owner" | "admin" | "member" };

/** Owners and admins only. */
export function listWorkspaceMembers(token: string, organizationId: string) {
  return organizationRequest<WorkspaceMember[]>(token, `organizations/${organizationId}/members`);
}

/** Owner only. Ownership itself cannot be changed here. */
export function changeWorkspaceMemberRole(token: string, organizationId: string, userId: string, role: "admin" | "member") {
  return organizationRequest<WorkspaceMember>(token, `organizations/${organizationId}/members/${userId}`, "PATCH", { role });
}

/** Owner only. Owners cannot be removed. */
export function removeWorkspaceMember(token: string, organizationId: string, userId: string) {
  return organizationRequest<void>(token, `organizations/${organizationId}/members/${userId}`, "DELETE");
}

/** For accounts without a password (WhatsApp or Google): add one, plus an email if the account has none. */
export async function setAccountCredentials(token: string, password: string, email?: string): Promise<AuthResponse> {
  return postJson<AuthResponse>("set-credentials", email ? { email, password } : { password }, token);
}
