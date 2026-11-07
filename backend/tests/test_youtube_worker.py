from app.modules.posting.youtube_worker import _derive_status


def test_youtube_worker_marks_successful_processing_as_published() -> None:
    assert _derive_status({
        "status": {"uploadStatus": "processed"},
        "processingDetails": {"processingStatus": "succeeded"},
    }) == ("published", None)


def test_youtube_worker_preserves_processing_state() -> None:
    assert _derive_status({
        "status": {"uploadStatus": "uploaded"},
        "processingDetails": {"processingStatus": "processing"},
    }) == ("processing", None)


def test_youtube_worker_records_provider_failure_reason() -> None:
    assert _derive_status({
        "status": {"uploadStatus": "rejected", "rejectionReason": "claim"},
        "processingDetails": {},
    }) == ("failed", "claim")


def test_youtube_worker_uses_safe_fallback_failure_reason() -> None:
    assert _derive_status({
        "status": {"uploadStatus": "failed"},
        "processingDetails": {},
    }) == ("failed", "YouTube processing failed")
