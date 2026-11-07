from app.core.network import resolve_client_ip


def test_without_trusted_proxies_the_forwarded_header_is_ignored() -> None:
    assert resolve_client_ip("6.6.6.6", "10.0.0.1", 0) == "10.0.0.1"


def test_one_trusted_proxy_uses_last_entry_not_forgeable_first_entry() -> None:
    # The client sent a fake first entry; the trusted proxy appended the real address last.
    assert resolve_client_ip("6.6.6.6, 203.0.113.9", "10.0.0.1", 1) == "203.0.113.9"


def test_two_trusted_proxies_use_second_entry_from_the_end() -> None:
    assert resolve_client_ip("6.6.6.6, 203.0.113.9, 172.16.0.5", "10.0.0.1", 2) == "203.0.113.9"


def test_missing_or_short_header_falls_back_to_direct_address() -> None:
    assert resolve_client_ip(None, "10.0.0.1", 1) == "10.0.0.1"
    assert resolve_client_ip("203.0.113.9", "10.0.0.1", 2) == "10.0.0.1"
