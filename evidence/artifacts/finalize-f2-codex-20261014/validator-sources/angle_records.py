# Verbatim selected definitions: native-agent-stack@252babe4040e39173cc178317c67699371806df6 scripts/angle_records.py

UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")

class AngleRecordError(ValueError):
    """An angle record fails the schema or evidence contract."""

def timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not UTC_TIMESTAMP.fullmatch(value):
        raise AngleRecordError("invalid UTC timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AngleRecordError("invalid UTC timestamp") from None
