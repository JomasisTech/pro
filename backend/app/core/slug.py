"""Helpers for building unique, URL-safe organization slugs."""

import re
from uuid import uuid4


def build_organization_slug(name: str) -> str:
    """Return a URL-safe slug with a short random suffix so identical business names never collide."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].strip("-") or "workspace"
    return f"{base}-{uuid4().hex[:8]}"
