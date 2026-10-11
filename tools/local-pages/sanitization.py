"""Shared page text projection from the native portable recipe.

Reference implementation: tools/north-star/build_readiness.py render.portable
at 164c071fec2e78d738746b73c4c4768e83cf1c62, lines 364-375. The native
home/UUID/task substitutions and recursive value semantics are retained here
because that nested helper is not an importable API. No native reader is loaded.
Account filtering comes from tools/local-pages/build_pages.py ACCOUNT_URL at
the same pin; urllib.parse supplies host/path normalization for owner links.
Email addresses are omitted after the same per-token decoding, so percent and
HTML-entity forms are matched in their decoded text. The decoders are CPython's
own, cited at the v3.13.16 mirror (cbc944f4bc59639a444dd971c737788ba2283a91):
html.unescape (Lib/html/__init__.py:118 accepts a reference without its
semicolon, :122), whose HTML5 table maps 'commat;' to '@' and 'period;' to '.'
(Lib/html/entities.py:567, :1736), and urllib.parse.unquote (Lib/urllib/parse.py:694).
A token over 4,096 characters is not decoded, so the mask also matches the
encoded at-sign and dot forms in place (%40, %2540, &#64 with or without its
semicolon, &#x40, &commat;, %2E, &#46 and &period;), as the b209afe8 page-local
mask did for %40 and &#64;. A name ending in a systemd unit type
(systemd.unit(5)), such as git-maintenance@daily.timer, is not an address.
"""

import base64
import binascii
from html import unescape
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote, urlsplit


ACCOUNT_URL = re.compile(r"https?://(?:claude\.ai/artifact|chatgpt\.com/|chat\.openai\.com/)[^\s<>\"']*", re.I)
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_HOME = re.compile(r"/home/[^/\s\"'<>]+|/Users/[^/\s\"'<>]+")
_SESSION = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
_TASK = re.compile(r"task-[a-z0-9]{8}-[a-z0-9]{6}", re.I)
_TOKEN = re.compile(r"[^\s<>\"']+")
_AT = r"(?:@|%(?:25)?40|&#0*64;?|&#[xX]0*40;?|&commat;)"
_DOT = r"(?:\.|%(?:25)?2[Ee]|&#0*46;?|&#[xX]0*2[Ee];?|&period;)"
# A systemd template-unit instance (git-maintenance@daily.timer) ends in a unit type, never a top-level domain;
# the types are systemd.unit(5)'s at systemd 259.
_UNIT = r"(?:service|socket|device|mount|automount|swap|target|path|timer|slice|scope)(?![A-Za-z])"
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+" + _AT + r"[A-Za-z0-9-]+(?:" + _DOT + r"[A-Za-z0-9-]+)*" + _DOT + r"(?!" + _UNIT + r")[A-Za-z]{2,}")
_PRESERVED = re.compile(r"\$\{(?:USER_HOME|LOCAL_SESSION_ID|LOCAL_TASK_HANDLE)\}|\[personal identifier omitted\]|\[account artifact omitted\]|\[email omitted\]|native-agent-stack-1a")


def _home_name() -> str | None:
    """Read only the supported home-path identity, never environment files."""
    value = Path.home().name
    return value if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,119}", value) else None


def _identity_pattern(name: str | None):
    # Separators in host/role labels include underscores. Ordinary longer words
    # and very short home names do not establish a personal-identity match.
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", re.I) if name and len(name) >= 3 else None


def _without_preserved(value: str) -> str:
    return _PRESERVED.sub("", value)


def _private(value: str, identity) -> bool:
    return bool(_HOME.search(value) or _SESSION.search(value) or _TASK.search(value) or _EMAIL.search(value) or is_account_url(value) or identity and identity.search(_without_preserved(value)))


def _project_identity(value: str, identity) -> str:
    """Keep published placeholders while masking every other name occurrence."""
    projected, offset = [], 0
    for match in _PRESERVED.finditer(value):
        projected.append(identity.sub("[personal identifier omitted]", value[offset:match.start()]))
        projected.append(match.group())
        offset = match.end()
    projected.append(identity.sub("[personal identifier omitted]", value[offset:]))
    return "".join(projected)


def _encoded_token(token: str, identity) -> str:
    """Omit an encoded token only when its decoded text matches the policy."""
    if len(token) > 4096:
        return token
    decoded = token
    for _ in range(2):
        decoded = unescape(unquote(decoded))
        decoded = re.sub(r"\\u([a-fA-F0-9]{4})|\\x([a-fA-F0-9]{2})", lambda match: chr(int(match.group(1) or match.group(2), 16)), decoded)
    if decoded != token and _private(decoded, identity):
        return _portable_text(decoded, identity)
    candidate = None
    try:
        if len(token) >= 12 and len(token) % 2 == 0 and re.fullmatch(r"[a-fA-F0-9]+", token):
            candidate = bytes.fromhex(token).decode("utf-8")
        elif 12 <= len(token) <= 4096 and re.fullmatch(r"[A-Za-z0-9_+/-]+={0,2}", token):
            candidate = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True).decode("utf-8")
    except (ValueError, UnicodeError, binascii.Error):
        pass
    return _portable_text(candidate, identity) if candidate is not None and _private(candidate, identity) else token


def _portable_text(value: str, identity) -> str:
    """Retain the native portable substitutions and surrounding source text."""
    value = _HOME.sub("${USER_HOME}", value)
    value = _SESSION.sub("${LOCAL_SESSION_ID}", value)
    value = _TASK.sub("${LOCAL_TASK_HANDLE}", value)
    value = _EMAIL.sub("[email omitted]", value)
    if identity:
        value = _project_identity(value, identity)
    value = ACCOUNT_URL.sub("[account artifact omitted]", value)
    return _URL.sub(lambda match: "[account artifact omitted]" if is_account_url(match.group()) else match.group(), value)


def is_account_url(value: Any) -> bool:
    """Classify the existing account-artifact scope using parsed URLs."""
    if not isinstance(value, str):
        return False
    if ACCOUNT_URL.search(value):
        return True
    try:
        parsed = urlsplit(value)
        host = unquote(parsed.hostname or "").lower()
        path = unquote(parsed.path).lower()
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and (host in {"chatgpt.com", "chat.openai.com"} or host == "claude.ai" and path.startswith("/artifact"))


def sanitize(value: Any) -> Any:
    """Project source values without changing the input or reading any files."""
    if isinstance(value, str):
        identity = _identity_pattern(_home_name())
        value = _TOKEN.sub(lambda match: _encoded_token(match.group(), identity), value)
        return _portable_text(value, identity)
    if isinstance(value, dict):
        return {key: sanitize(child) for key, child in value.items()}
    if isinstance(value, list):
        return [sanitize(child) for child in value]
    return value


def text(value: Any) -> str:
    """Normalize a page label after applying the shared source projection."""
    return sanitize(str(sanitize(value) if value is not None else "Unspecified in source"))
