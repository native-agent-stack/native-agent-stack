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


def private_digest_prefix_locations(publication, private_digests, minimum=7):
    """Accept a private input set without embedding it in any public blacklist."""
    if type(minimum) is not int or not 7 <= minimum <= 64:
        raise ValueError("invalid_private_prefix_length")
    values=list(private_digests)
    if any(not isinstance(value,str) or not DIGEST.fullmatch(value.lower()) for value in values):
        raise ValueError("invalid_private_digest")
    heads={value[:minimum].lower().encode() for value in values}
    return [(path,number) for path,data in sorted(publication.items())
            for number,line in enumerate(data.splitlines(),1)
            if any(head in line.lower() for head in heads)]
