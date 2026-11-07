"""Helpers for working out the real client address behind reverse proxies."""


def resolve_client_ip(forwarded_for: str | None, direct_host: str, trusted_proxy_count: int) -> str:
    """Return the client address to use for rate limiting.

    With no trusted proxies, only the direct connection address is believable. When the app runs
    behind `trusted_proxy_count` proxies that each append to X-Forwarded-For, the address they
    recorded is the Nth entry counted from the END of the header. Entries further left can be
    forged by the client, so they are never used.
    """
    if trusted_proxy_count <= 0 or not forwarded_for:
        return direct_host
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    if len(hops) < trusted_proxy_count:
        return direct_host
    return hops[-trusted_proxy_count]
