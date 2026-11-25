from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a naive UTC timestamp matching the project’s existing DB conventions."""
    return datetime.now(timezone.utc).replace(tzinfo=None)