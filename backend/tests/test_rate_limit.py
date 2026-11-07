from app.core.rate_limit import FailedAttemptLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_max_failures_and_reports_wait_time() -> None:
    clock = FakeClock()
    limiter = FailedAttemptLimiter(max_attempts=3, window_seconds=60, clock=clock)
    for _ in range(2):
        limiter.record_failure("a")
    assert limiter.retry_after("a") == 0
    limiter.record_failure("a")
    assert limiter.retry_after("a") == 60
    clock.now += 20
    assert limiter.retry_after("a") == 40


def test_block_expires_after_the_window() -> None:
    clock = FakeClock()
    limiter = FailedAttemptLimiter(max_attempts=2, window_seconds=60, clock=clock)
    limiter.record_failure("a")
    limiter.record_failure("a")
    assert limiter.retry_after("a") > 0
    clock.now += 61
    assert limiter.retry_after("a") == 0


def test_keys_are_independent_and_reset_clears_a_key() -> None:
    limiter = FailedAttemptLimiter(max_attempts=1, window_seconds=60, clock=FakeClock())
    limiter.record_failure("a")
    assert limiter.retry_after("a") > 0
    assert limiter.retry_after("b") == 0
    limiter.reset("a")
    assert limiter.retry_after("a") == 0


def _small_limiter(monkeypatch, cap: int, max_attempts: int = 2):
    import app.core.rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module, "_MAX_TRACKED_KEYS", cap)
    clock = FakeClock()
    return clock, FailedAttemptLimiter(max_attempts=max_attempts, window_seconds=60, clock=clock)


def test_memory_stays_bounded_by_evicting_oldest_unblocked_key(monkeypatch) -> None:
    clock, limiter = _small_limiter(monkeypatch, cap=2, max_attempts=3)
    limiter.record_failure("older")
    clock.now += 1
    limiter.record_failure("newer")
    clock.now += 1
    limiter.record_failure("incoming")

    assert len(limiter._failures) == 2
    assert "older" not in limiter._failures
    assert "newer" in limiter._failures
    assert "incoming" in limiter._failures


def test_flooding_new_keys_cannot_evict_an_active_block(monkeypatch) -> None:
    clock, limiter = _small_limiter(monkeypatch, cap=3, max_attempts=2)
    limiter.record_failure("victim")
    clock.now += 1
    limiter.record_failure("victim")
    assert limiter.retry_after("victim") > 0

    for index in range(50):
        clock.now += 0.01
        limiter.record_failure(f"attacker-{index}")

    assert limiter.retry_after("victim") > 0
    assert len(limiter._failures) <= 3


def test_recent_activity_protects_a_key_from_eviction(monkeypatch) -> None:
    clock, limiter = _small_limiter(monkeypatch, cap=2, max_attempts=5)
    limiter.record_failure("a")
    clock.now += 1
    limiter.record_failure("b")
    clock.now += 1
    limiter.record_failure("a")  # "a" is now the most recently active key
    clock.now += 1
    limiter.record_failure("c")

    assert "a" in limiter._failures
    assert "b" not in limiter._failures


def test_high_failure_count_survives_a_flood_of_low_count_keys(monkeypatch) -> None:
    clock, limiter = _small_limiter(monkeypatch, cap=3, max_attempts=5)
    for _ in range(3):
        limiter.record_failure("victim")  # oldest key, but holds 3 of 5 failures
        clock.now += 1
    for index in range(100):
        clock.now += 0.01
        limiter.record_failure(f"attacker-{index}")  # one failure each

    assert len(limiter._failures) <= 3
    assert len(limiter._failures["victim"]) == 3


def test_shared_overflow_budget_when_table_is_full_of_blocked_keys(monkeypatch) -> None:
    clock, limiter = _small_limiter(monkeypatch, cap=2, max_attempts=1)
    limiter.record_failure("x")
    clock.now += 1
    limiter.record_failure("y")
    limiter.record_failure("new-0")  # table is full of blocked keys: not tracked individually

    assert len(limiter._failures) == 2
    assert "new-0" not in limiter._failures
    # Normal users are not locked out while the shared budget lasts...
    assert limiter.retry_after("someone-else") == 0
    budget = limiter._overflow_max
    for index in range(1, budget):
        limiter.record_failure(f"new-{index}")
    # ...but the total number of guesses across all untracked keys is capped.
    assert len(limiter._overflow) == budget
    assert limiter.retry_after("any-untracked-key") > 0
    assert limiter.retry_after("x") > 0


def test_overflow_budget_recovers_and_reset_clears_saturation(monkeypatch) -> None:
    clock, limiter = _small_limiter(monkeypatch, cap=2, max_attempts=1)
    limiter.record_failure("x")
    clock.now += 1
    limiter.record_failure("y")
    for index in range(limiter._overflow_max):
        limiter.record_failure(f"new-{index}")
    assert limiter.retry_after("fresh") > 0

    limiter.reset("x")
    assert limiter.retry_after("fresh") == 0
    limiter.record_failure("fresh")
    assert "fresh" in limiter._failures

    clock.now += 120
    assert limiter.retry_after("fresh") == 0
    assert limiter.retry_after("y") == 0
