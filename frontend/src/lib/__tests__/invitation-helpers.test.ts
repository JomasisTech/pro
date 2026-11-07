import { describe, expect, it } from "vitest";
import { describeExpiry, invitationStatus, isOpenInvitation, sortInvitations } from "../invitation-helpers";

const base = { expires_at: "2026-11-10T00:00:00Z", accepted_at: null, created_at: "2026-11-01" };
const NOW = new Date("2026-11-04T12:00:00Z");

describe("invitation helpers", () => {
  it("prefers the server status and derives one when it is missing", () => {
    expect(invitationStatus({ ...base, status: "accepted" }, NOW)).toBe("accepted");
    expect(invitationStatus(base, NOW)).toBe("pending");
    expect(invitationStatus({ ...base, expires_at: "2026-11-01T00:00:00Z" }, NOW)).toBe("expired");
    expect(invitationStatus({ ...base, accepted_at: "2026-11-02T00:00:00Z" }, NOW)).toBe("accepted");
  });
  it("treats only accepted invitations as closed", () => {
    expect(isOpenInvitation("pending") && isOpenInvitation("expired")).toBe(true);
    expect(isOpenInvitation("accepted")).toBe(false);
  });
  it("describes expiry in days", () => {
    expect(describeExpiry("2026-11-07T12:00:00Z", NOW)).toBe("Expires in 3 days");
    expect(describeExpiry("2026-11-05T12:00:00Z", NOW)).toBe("Expires in 1 day");
    expect(describeExpiry("2026-11-04T12:00:00Z", NOW)).toBe("Expires today");
    expect(describeExpiry("2026-11-02T12:00:00Z", NOW)).toBe("Expired 2 days ago");
  });
  it("lists open invitations before history, newest first", () => {
    const items = [
      { ...base, status: "accepted" as const, created_at: "2026-11-04" },
      { ...base, status: "pending" as const, created_at: "2026-11-01" },
      { ...base, status: "pending" as const, created_at: "2026-11-03" },
      { ...base, status: "expired" as const, created_at: "2026-11-02" },
    ];
    const sorted = sortInvitations(items, NOW);
    expect(sorted.map((item) => item.status)).toEqual(["pending", "pending", "expired", "accepted"]);
    expect(sorted[0].created_at).toBe("2026-11-03");
  });
});
