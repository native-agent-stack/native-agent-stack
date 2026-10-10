#!/usr/bin/env python3
"""One credential-free native GDELT DOC request; keep article rows host-local."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

from gdeltdoc import Filters, GdeltDoc


def main():
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=2)
    version = importlib.metadata.version("gdeltdoc")
    if version != "1.12.0":
        raise ValueError("gdeltdoc_pin_mismatch")
    query = Filters(start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d"),
                    keyword="stock market", num_records=10)
    try:
        rows = GdeltDoc().article_search(query)
    except Exception as error:
        print(json.dumps({"gdeltdoc": version, "status": "unavailable", "error_type": type(error).__name__,
                          "source": "https://api.gdeltproject.org/api/v2/doc/doc", "query": query.query_string}))
        return 1
    raw = rows.to_json(orient="records", date_format="iso").encode()
    private = Path.home() / ".cache/ns2604-catalyst-market-data-gaps/news/native-rows.json"
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_bytes(raw)
    print(json.dumps({"gdeltdoc": version, "status": "observed", "rows": len(rows), "fields": list(rows.columns),
                      "normalized_response_sha256": hashlib.sha256(raw).hexdigest(),
                      "retained_path": "~/.cache/ns2604-catalyst-market-data-gaps/news/native-rows.json",
                      "source": "https://api.gdeltproject.org/api/v2/doc/doc", "query": query.query_string,
                      "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                      "scope": "current public news metadata; no publisher content, historical availability or licensed research qualification"}))
    return 0 if len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
