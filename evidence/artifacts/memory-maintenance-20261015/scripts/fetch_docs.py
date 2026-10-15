#!/usr/bin/env python3
"""Fetch named doc URLs with a curl/8 User-Agent, save them, append sha256 and UTC fetch time to MANIFEST.tsv."""
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

out_dir = Path(sys.argv[1])
manifest = out_dir.parent / "MANIFEST.tsv"
urls = sys.argv[2:]
out_dir.mkdir(parents=True, exist_ok=True)
new = not manifest.exists()
with manifest.open("a", encoding="utf-8") as mf:
    if new:
        mf.write("file\tsource\tsha256\tbytes\tfetched_utc\thttp_status\tfinal_url\n")
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        fetched = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            status = r.status
            final = r.geturl()
        name = url.rstrip("/").rsplit("/", 1)[-1]
        path = out_dir / name
        path.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        mf.write(f"docs/{name}\t{url}\t{digest}\t{len(body)}\t{fetched}\t{status}\t{final}\n")
        print(f"docs/{name}\t{digest}\t{len(body)}\t{fetched}\t{status}\t{final}")
