"""Content-addressed receipt digests must resolve to files in the published set."""
import hashlib
import re

DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def receipt_digests(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from receipt_digests(item, path + "/" + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from receipt_digests(item, path + "/" + str(index))
    elif isinstance(value, str) and DIGEST.fullmatch(value):
        yield path, value


def unpublished_digests(records, published_files):
    """No private-preimage guessing: a missing public preimage is itself a failure."""
    published = {hashlib.sha256(content).hexdigest() for content in published_files.values()}
    return [(record, field) for record, value in records.items()
            for field, digest in receipt_digests(value) if digest not in published]
