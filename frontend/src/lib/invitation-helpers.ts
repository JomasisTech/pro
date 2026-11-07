export type InvitationStatus = "pending" | "accepted" | "expired";

type InvitationLike = { status?: InvitationStatus; accepted_at: string | null; expires_at: string; created_at: string };

/** Prefer the server's status; derive it for older API responses that do not send one. */
export function invitationStatus(item: InvitationLike, now: Date = new Date()): InvitationStatus {
  if (item.status) return item.status;
  if (item.accepted_at) return "accepted";
  return new Date(item.expires_at) <= now ? "expired" : "pending";
}

export const STATUS_LABELS: Record<InvitationStatus, string> = { pending: "Pending", accepted: "Accepted", expired: "Expired" };

/** Pending and expired invitations can be re-sent or revoked; accepted ones are history. */
export const isOpenInvitation = (status: InvitationStatus) => status !== "accepted";

/** "Expires in 3 days", "Expires today", "Expired 2 days ago". */
export function describeExpiry(expiresAt: string, now: Date = new Date()): string {
  const diffDays = Math.round((new Date(expiresAt).getTime() - now.getTime()) / 86_400_000);
  if (diffDays === 0) return "Expires today";
  if (diffDays > 0) return `Expires in ${diffDays} day${diffDays === 1 ? "" : "s"}`;
  const ago = Math.abs(diffDays);
  return `Expired ${ago} day${ago === 1 ? "" : "s"} ago`;
}

/** Open invitations first (pending, then expired), history last; newest first inside each group. */
export function sortInvitations<T extends InvitationLike>(items: T[], now: Date = new Date()): T[] {
  const rank: Record<InvitationStatus, number> = { pending: 0, expired: 1, accepted: 2 };
  return [...items].sort((a, b) => rank[invitationStatus(a, now)] - rank[invitationStatus(b, now)] || b.created_at.localeCompare(a.created_at));
}
