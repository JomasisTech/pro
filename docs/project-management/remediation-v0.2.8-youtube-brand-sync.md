# Remediation v0.2.8 — YouTube Brand Intelligence sync

**Date:** 2026-11-04

## Scope

Complete the YouTube read side of the existing Brand Intelligence social-observation workflow. This is a manual-trigger synchronization slice; it does not add scheduled jobs or claim production verification.

## Changes

- Added `backend/app/integrations/youtube_media.py` using the official YouTube Data API. It resolves the authenticated channel's uploads playlist, requests up to 20 latest items, and normalizes video ID, title/description, timestamp, and watch URL.
- Expanded Google OAuth scopes to include `https://www.googleapis.com/auth/youtube.readonly` while retaining `youtube.upload`.
- Added YouTube dispatch to the existing organization-scoped Brand Intelligence sync endpoint. It checks the read scope, uses the existing encrypted credential and token-refresh flow, and shares the established observation upsert/provenance/activity-log path.
- Enabled YouTube sync in the Brand Intelligence frontend and distinguishes retrieved videos from posts.
- Added provider adapter, sync/upsert, scope-gating, and OAuth-scope regression coverage.

## Verification

Command: `DATABASE_URL=sqlite+pysqlite:///:memory: pytest -q tests/test_youtube_media_sync.py tests/test_social_oauth.py tests/test_youtube_publishing.py tests/test_youtube_worker.py`

Result: **19 passed in 4.61s**.

Command: `python -m compileall -q backend/app backend/tests`

Result: passed.

Tests use SQLite and mocked provider responses. No live Google/YouTube requests were made.

## Deployment and limitations

- Existing connected YouTube accounts need to reconnect and grant `youtube.readonly`.
- Confirm the OAuth consent screen's configured scopes and Google verification requirements before production use.
- Live provider verification, PostgreSQL migration/integration validation, frontend dependency installation/lint/build, browser testing, durable background sync, and production deployment remain outstanding.
- The sync is manually triggered. This increment does not create a recurring scheduler or background job.
