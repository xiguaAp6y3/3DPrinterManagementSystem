from datetime import datetime, timedelta, timezone


UTC8 = timezone(timedelta(hours=8))


def utc8_now() -> datetime:
    return datetime.now(UTC8).replace(tzinfo=None)
