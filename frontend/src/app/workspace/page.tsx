"use client";

import { Select } from "@/components/select";
import { STATUS_LABELS, describeExpiry, invitationStatus, isOpenInvitation, sortInvitations } from "@/lib/invitation-helpers";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorNote, SuccessNote, inputClass, primaryButtonClass } from "@/components/auth-shell";
import {
  deleteWorkspace,
  fetchMyOrganizations,
  getAccessToken,
  getStoredOrganization,
  renameWorkspace,
  saveActiveOrganization,
  type AuthOrganization,
  type WorkspaceInvitation,
  listWorkspaceInvitations,
  inviteWorkspaceMember,
  revokeWorkspaceInvitation,
  resendWorkspaceInvitation,
  type WorkspaceMember,
  listWorkspaceMembers,
  changeWorkspaceMemberRole,
  removeWorkspaceMember,
} from "@/lib/auth";

export default function WorkspaceSettingsPage() {
  const router = useRouter();
  const [organization, setOrganization] = useState<AuthOrganization | null>(null);
  const [name, setName] = useState("");
  const [confirmName, setConfirmName] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member");
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);

  useEffect(() => {
    const active = getStoredOrganization();
    if (!getAccessToken() || !active) {
      router.replace("/login");
      return;
    }
    setOrganization(active);
    setName(active.name);
    if (active.role === "owner" || active.role === "admin") {
      listWorkspaceInvitations(getAccessToken()!, active.id).then(setInvitations).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load invitations."));
      listWorkspaceMembers(getAccessToken()!, active.id).then(setMembers).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load members."));
    }
  }, [router]);

  async function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getAccessToken();
    if (!token || !organization) return router.replace("/login");
    setError("");
    setNotice("");
    setBusy("rename");
    try {
      const updated = await renameWorkspace(token, organization.id, name.trim());
      saveActiveOrganization(updated);
      setOrganization(updated);
      setName(updated.name);
      setNotice("Workspace renamed.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't rename the workspace. Please try again.");
    } finally {
      setBusy("");
    }
  }

  async function handleInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getAccessToken();
    if (!token || !organization) return router.replace("/login");
    setBusy("invite"); setError(""); setNotice("");
    try {
      const result = await inviteWorkspaceMember(token, organization.id, inviteEmail.trim(), inviteRole);
      setNotice(result.message); setInviteEmail("");
      setInvitations(await listWorkspaceInvitations(token, organization.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not send invitation."); }
    finally { setBusy(""); }
  }

  async function handleResend(invitationId: string) {
    const token = getAccessToken();
    if (!token || !organization) return;
    setBusy(`resend-${invitationId}`); setError(""); setNotice("");
    try {
      const result = await resendWorkspaceInvitation(token, organization.id, invitationId);
      setNotice(result.message);
      setInvitations(await listWorkspaceInvitations(token, organization.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not resend invitation."); }
    finally { setBusy(""); }
  }

  async function handleRevoke(invitationId: string) {
    const token = getAccessToken();
    if (!token || !organization) return;
    setBusy(invitationId); setError(""); setNotice("");
    try {
      await revokeWorkspaceInvitation(token, organization.id, invitationId);
      setInvitations((items) => items.filter((item) => item.id !== invitationId));
      setNotice("Invitation revoked.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not revoke invitation."); }
    finally { setBusy(""); }
  }

  async function handleRoleChange(member: WorkspaceMember, role: "admin" | "member") {
    const token = getAccessToken();
    if (!token || !organization || member.role === role) return;
    setBusy(`role-${member.user_id}`); setError(""); setNotice("");
    try {
      const updated = await changeWorkspaceMemberRole(token, organization.id, member.user_id, role);
      setMembers((items) => items.map((item) => (item.user_id === updated.user_id ? updated : item)));
      setNotice(`${updated.full_name} is now ${updated.role === "admin" ? "an admin" : "a member"}.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not change role."); }
    finally { setBusy(""); }
  }

  async function handleRemoveMember(member: WorkspaceMember) {
    const token = getAccessToken();
    if (!token || !organization) return;
    if (!window.confirm(`Remove ${member.full_name} from ${organization.name}?`)) return;
    setBusy(`remove-${member.user_id}`); setError(""); setNotice("");
    try {
      await removeWorkspaceMember(token, organization.id, member.user_id);
      setMembers((items) => items.filter((item) => item.user_id !== member.user_id));
      setNotice(`${member.full_name} was removed from the workspace.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not remove member."); }
    finally { setBusy(""); }
  }

  async function handleDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getAccessToken();
    if (!token || !organization) return router.replace("/login");
    setError("");
    setNotice("");
    setBusy("delete");
    try {
      await deleteWorkspace(token, organization.id, confirmName);
      const remaining = await fetchMyOrganizations(token);
      if (remaining.length > 0) saveActiveOrganization(remaining[0]);
      window.location.assign("/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't delete the workspace. Please try again.");
      setBusy("");
    }
  }

  if (!organization) return null;
  const isOwner = organization.role === "owner";

  return (
    <div className="mx-auto w-full max-w-xl space-y-8 px-4 py-6 sm:px-6">
      <section>
        <h1 className="text-2xl font-extrabold tracking-tight">Workspace settings</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">Settings for <strong>{organization.name}</strong>. Your role here: {organization.role}.</p>
      </section>

      {error ? <ErrorNote>{error}</ErrorNote> : null}
      {notice ? <SuccessNote>{notice}</SuccessNote> : null}

      {organization.role === "owner" || organization.role === "admin" ? (
        <section className="space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <div><h2 className="text-lg font-bold">Invite teammates</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Invite people by email. Invitations expire after seven days.</p></div>
            <form onSubmit={handleInvite} className="grid gap-3 sm:grid-cols-[1fr_130px_auto]">
              <input aria-label="Teammate email" type="email" required value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} placeholder="teammate@example.com" className={inputClass} />
              <Select aria-label="Invitation role" value={inviteRole} onChange={(event) => setInviteRole(event.target.value as "admin" | "member")} className={inputClass}>
                <option value="member">Member</option>{isOwner ? <option value="admin">Admin</option> : null}
              </Select>
              <button type="submit" disabled={busy !== ""} className={primaryButtonClass}>{busy === "invite" ? "Sending…" : "Send invite"}</button>
            </form>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">Invitation history</h3>
              {invitations.length === 0 ? <p className="text-sm text-[var(--color-text-muted)]">No invitations yet.</p> : sortInvitations(invitations).map((item) => {
                const status = invitationStatus(item);
                return (
                  <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] p-3">
                    <div className="min-w-0"><p className="break-all text-sm font-semibold">{item.email}</p><p className="text-xs text-[var(--color-text-muted)]">{item.role} · {STATUS_LABELS[status]}{status !== "accepted" ? ` · ${describeExpiry(item.expires_at)}` : ""}</p></div>
                    {isOpenInvitation(status) ? (
                      <div className="flex gap-4">
                        <button type="button" onClick={() => handleResend(item.id)} disabled={busy !== ""} className="text-sm font-semibold text-[var(--auth-accent)] disabled:opacity-50">{busy === `resend-${item.id}` ? "Sending…" : "Resend"}</button>
                        <button type="button" onClick={() => handleRevoke(item.id)} disabled={busy !== ""} className="text-sm font-semibold text-[var(--color-danger)] disabled:opacity-50">{busy === item.id ? "Revoking…" : "Revoke"}</button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
        </section>
      ) : null}

      {organization.role === "owner" || organization.role === "admin" ? (
        <section className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <div><h2 className="text-lg font-bold">Members</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">{isOwner ? "Change roles or remove people. Ownership cannot be transferred here." : "People with access to this workspace. Only the owner can change roles or remove members."}</p></div>
          {members.length === 0 ? <p className="text-sm text-[var(--color-text-muted)]">No members loaded.</p> : (
            <ul className="space-y-2">
              {members.map((member) => (
                <li key={member.user_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] p-3">
                  <div className="min-w-0"><p className="break-words text-sm font-semibold">{member.full_name}</p><p className="break-all text-xs text-[var(--color-text-muted)]">{member.email || "No email"}</p></div>
                  {isOwner && member.role !== "owner" ? (
                    <div className="flex items-center gap-3">
                      <Select aria-label={`Role for ${member.full_name}`} value={member.role} disabled={busy !== ""} onChange={(event) => handleRoleChange(member, event.target.value as "admin" | "member")} className={`${inputClass} !w-auto !py-2`}>
                        <option value="member">Member</option><option value="admin">Admin</option>
                      </Select>
                      <button type="button" onClick={() => handleRemoveMember(member)} disabled={busy !== ""} className="text-sm font-semibold text-[var(--color-danger)] disabled:opacity-50">{busy === `remove-${member.user_id}` ? "Removing…" : "Remove"}</button>
                    </div>
                  ) : <span className="rounded-full bg-[var(--color-page)] px-3 py-1 text-xs font-semibold capitalize">{member.role}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {!isOwner ? (
        <p className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-sm leading-6 text-[var(--color-text-muted)]">Only the workspace owner can rename or delete it.</p>
      ) : (
        <>
          <form onSubmit={handleRename} className="space-y-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <h2 className="text-lg font-bold">Rename workspace</h2>
            <div>
              <label htmlFor="workspace-name" className="mb-2 block text-sm font-semibold">Workspace name</label>
              <input id="workspace-name" required minLength={2} maxLength={160} value={name} onChange={(event) => setName(event.target.value)} className={inputClass} />
            </div>
            <button type="submit" disabled={busy !== "" || name.trim() === organization.name} className={primaryButtonClass}>{busy === "rename" ? "Saving…" : "Save name"}</button>
          </form>

          <form onSubmit={handleDelete} className="space-y-4 rounded-2xl border border-[var(--color-danger)]/40 bg-[var(--color-surface)] p-6">
            <h2 className="text-lg font-bold text-[var(--color-danger)]">Delete workspace</h2>
            <p className="text-sm leading-6 text-[var(--color-text-muted)]">Permanently deletes this workspace with its business profile, drafts, scheduled posts, connected social accounts, media and activity log. This cannot be undone. You can&apos;t delete your only workspace.</p>
            <div>
              <label htmlFor="confirm-workspace-name" className="mb-2 block text-sm font-semibold">Type <strong>{organization.name}</strong> to confirm</label>
              <input id="confirm-workspace-name" required value={confirmName} onChange={(event) => setConfirmName(event.target.value)} autoComplete="off" className={inputClass} />
            </div>
            <button type="submit" disabled={busy !== "" || confirmName.trim() !== organization.name} className="w-full rounded-xl bg-[var(--color-danger)] px-4 py-3.5 text-sm font-bold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60">{busy === "delete" ? "Deleting…" : "Delete this workspace"}</button>
          </form>
        </>
      )}
    </div>
  );
}
