"""Shared page text projection from the native portable recipe.

Reference implementation: tools/north-star/build_readiness.py render.portable
at 164c071fec2e78d738746b73c4c4768e83cf1c62, lines 364-375. The native
home/UUID/task substitutions and recursive value semantics are retained here
because that nested helper is not an importable API. No native reader is loaded.
Account filtering comes from tools/local-pages/build_pages.py ACCOUNT_URL at
the same pin; urllib.parse supplies host/path normalization for owner links.
Email addresses are omitted after the same per-token decoding, so percent and
HTML-entity forms are matched in their decoded text. The match is anchored at
the at sign and its domain, then takes the whole local part that ends there, in
either form RFC 5322 section 3.4.1 allows: any nonempty run of atext (letters,
digits and !#$%&'*+-/=?^_`{|}~ with dots, so !!!@d and /@d are addresses), or a
quoted string such as "reviewer", "john doe" or the empty "", whose quotes may be
percent- or entity-encoded in place or JSON-escaped as \". CPython's own address
parser accepts all of these (Lib/email/_parseaddr.py at the mirror named below:
getaddrspec, lines 365-385, reads atoms through getatom, lines 475-493, and
quoted strings through getquote, line 463, whose getdelimited loop, lines
426-461, ends an empty one at line 449). The slash and the backtick are atext
like the rest, and three contexts are set aside, each positively identified
(<at> stands for the at sign in the examples, so this file writes no address):
inside a URL (a scheme, "://", and every character up to a space, an angle
bracket or a quote) the slash ends the local part, so https://medium.com/<at>handle.name
is a path, not an address, while https://example.org/path/NAME<at>HOST still masks
from NAME; an at sign that comes right after a slash, with a name after it that a
slash or an opening parenthesis follows, starts a path segment or a call, as in
run_stream_events/<at>agent.tool/message_history and <at>DBOS.workflow()/<at>DBOS.step()
(the slash must be the character right before the at sign, which no mailbox has,
so an address that is itself a path segment, such as gcloud's
legacy_credentials/NAME<at>HOST/adc.json, masks whole with its directory prefix);
and a backtick string that does not follow a letter or digit and that a backtick
string of equal length closes after the at sign opens a Markdown code span
(CommonMark 0.31.2 section 6.1), so `@AGENTS.md` is not an address and a code span
around an address keeps its backticks. A backtick string that nothing closes there
is part of the local part, and so is a slash anywhere else: /<at>d, x/<at>d and a
host path with no scheme and nothing after it (medium.com/<at>handle.name) are
addresses and are masked. The
mask reads the whole text with each token decoded, so a local part that a
quote, a space or an apostrophe splits across tokens is found whole. Text that
decoding leaves unchanged is masked exactly from the start of the local part to
the end of the domain; a token that decoding changes is omitted whole when the
address touches it; overlapping matches merge from their earliest start, so a
quoted local part that itself holds an at sign is omitted whole. From each at
sign the walk back over atext stops after 256 characters (RFC 5321 section
4.5.3.1.1 limits a local part to 64 octets) and never passes the address before
it, so the cost is linear in the text's length: three adversarial
50,000-character forms (%40 and &#64 written in atext, and apostrophe-joined
%252540 tokens) each take under 0.5 s. A local part over 256 characters keeps
its leading part visible. After masking, a value that still holds an at sign,
raw or encoded, followed by a domain and directly after a word character, or
after a quote with only whitespace between, is dropped whole and replaced by
RESIDUE_OMITTED, so a form the mask cannot classify fails closed. The decoders
are CPython's own, cited at the v3.13.16 mirror
(cbc944f4bc59639a444dd971c737788ba2283a91):
html.unescape (Lib/html/__init__.py:118 accepts a reference without its
semicolon, :122), whose HTML5 table maps 'commat;' to '@' and 'period;' to '.'
(Lib/html/entities.py:567, :1736), and urllib.parse.unquote (Lib/urllib/parse.py:694).
A token over 4,096 characters is not decoded, so the mask also matches these
encoded forms in place, as the b209afe8 page-local mask did for %40 and &#64;:
for the at sign %40, %2540, &#64 and &#x40 (each reference with or without its
semicolon) and &commat;, for the dot %2E, %252E, &#46, &#x2E and &period;, and
for the quotes of a quoted local part ", %22, %2522, &quot, &#34 and &#x22 (each
reference with or without its semicolon). Other encodings in such a token, such
as &amp;#64; or %26%2364%3B, stay as written. A name ending in one of ten systemd unit types (systemd.unit(5):
service, socket, device, mount, automount, swap, path, timer, slice and scope),
such as git-maintenance@daily.timer, is not an address, except an instance name
that itself contains a dot, which still masks (openvpn-client@site.conf.service
becomes "[email omitted].service"; #1012 Follow-ups, the bdc09788 micro's (a)5). The eleventh,
target, is also a delegated top-level domain, so a name ending in it is masked.
"""

import base64
import binascii
from bisect import bisect_left, bisect_right
from functools import lru_cache
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
# A systemd template-unit instance (git-maintenance@daily.timer) ends in a unit type. Ten of the eleven types in
# systemd.unit(5) at systemd 259 are exempt. `target` is not: it is also a delegated top-level domain
# (public_suffix_list.dat), and a test checks this list against the installed public suffix list.
_UNIT_TYPES = ("service", "socket", "device", "mount", "automount", "swap", "path", "timer", "slice", "scope")
_UNIT = r"(?:" + "|".join(_UNIT_TYPES) + r")(?![A-Za-z])"
_DOMAIN = r"[A-Za-z0-9-]+(?:" + _DOT + r"[A-Za-z0-9-]+)*" + _DOT + r"(?!" + _UNIT + r")[A-Za-z]{2,}"
_ADDRESS_TAIL = re.compile(_AT + _DOMAIN)
RESIDUE_OMITTED = "[value omitted: an at sign beside a word remained after masking]"
# RFC 5322 3.2.3 atext, all 81 characters, plus the dot of a dot-atom, and 3.2.4 quoted strings, whose quotes may be encoded
# in place. The slash and the backtick are atext; _local_start names the three contexts that set them aside.
_ATEXT = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-/=?^_`{|}~.")
_SCHEME = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-.")
_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_URL_BODY = re.compile(r"[^\s<>\"']*")
_TICKS = re.compile(r"`+")
_QUOTE = r'(?:"|%(?:25)?22|&quot;?|&#0*34;?|&#[xX]0*22;?)'
# After masking, an at sign, raw or encoded, followed by a domain and directly after a word character, or after a
# quote with only whitespace between, is residue the mask could not classify (whitespace before the at sign, a
# quoted local part over 256 characters): the value is dropped instead. Prose such as "imports @AGENTS.md" or
# "pin @ 2.0.0" has a space after a word, not a quote, so it stays.
_AT_FORMS = r"(?:@|%(?:25)?40|&#0*64;?|&#[xX]0*40;?|&commat;|\\u0040)"
_RESIDUE = re.compile(r"(?:\w|(?:" + _QUOTE + r"|'|\\\")\s*)" + _AT_FORMS + _DOMAIN)
_OMITTED = "[email omitted]"
# RFC 5321 4.5.3.1.1 limits a local part to 64 octets; the walk back from an at sign stops after 256 characters,
# which leaves room for encodings, so a run of atext never costs more than that per at sign.
_LOCAL_PART_LIMIT = 256
# A JSON-serialized string writes the quotes of "w1 w2"@d.example.org as \", so an escaped quote also opens and
# closes a quoted local part. Content excludes the escaped quote, so each character has one parse.
_ESCAPED_QUOTED_LOCAL = re.compile(r'\\"(?:(?!\\")[^\r\n]){0,256}\\"\Z')
# A backslash always opens a quoted pair, so each character has one parse and the search stays linear in the window.
_QUOTED_LOCAL = re.compile(_QUOTE + r"(?:\\.|(?!" + _QUOTE + r")[^\\\r\n]){0,256}" + _QUOTE + r"\Z")
_PRESERVED = re.compile(r"\$\{(?:USER_HOME|LOCAL_SESSION_ID|LOCAL_TASK_HANDLE)\}|\[personal identifier omitted\]|\[account artifact omitted\]|\[email omitted\]|\[value omitted: an at sign beside a word remained after masking\]|native-agent-stack-1a")


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


def _url_spans(value: str) -> list[tuple[int, int]]:
    """Each URL in the text as (start, end): a scheme (RFC 3986 section 3.1), "://", and every character up to a space, an
    angle bracket or a quote. One pass: each "://" is found once and the scheme walk back is bounded."""
    spans, cursor = [], 0
    while (mark := value.find("://", cursor)) >= 0:
        begin = mark
        while begin > cursor and mark - begin < 32 and value[begin - 1] in _SCHEME:
            begin -= 1
        while begin < mark and value[begin] not in _LETTERS:
            begin += 1
        if begin == mark:
            cursor = mark + 3
            continue
        cursor = _URL_BODY.match(value, mark + 3).end()
        spans.append((begin, cursor))
    return spans


class _Context:
    """What the text around an at sign can set aside, each found once per text and only when a local part asks for it."""

    def __init__(self, value: str) -> None:
        self.value = value
        self._urls: tuple[list[int], list[int]] | None = None
        self._ticks: dict[int, list[int]] | None = None

    def in_url(self, index: int) -> bool:
        if self._urls is None:
            spans = _url_spans(self.value)
            self._urls = ([low for low, _ in spans], [high for _, high in spans])
        found = bisect_right(self._urls[0], index) - 1
        return found >= 0 and index < self._urls[1][found]

    def closes_after(self, opener_end: int, length: int, index: int) -> bool:
        """Whether the first backtick string of exactly `length` characters from opener_end on starts after index: a code
        span ends with a backtick string of equal length (CommonMark 0.31.2 section 6.1), so this one holds the at sign."""
        if self._ticks is None:
            self._ticks = {}
            for match in _TICKS.finditer(self.value):
                self._ticks.setdefault(match.end() - match.start(), []).append(match.start())
        starts = self._ticks.get(length, [])
        found = bisect_left(starts, opener_end)
        return found < len(starts) and starts[found] > index


def _local_start(value: str, at: int, end: int, floor: int = 0, context: _Context | None = None) -> int | None:
    """Where the local part ending at value[at], the at sign, begins: a quoted string, else a run of atext.

    `end` is where the domain after the at sign ends. The atext walk stops after _LOCAL_PART_LIMIT characters and never
    passes floor, the end of the address before it; a run that continues into that address is glued to it and starts at
    floor, so the two merge. The slash and the backtick are atext like the rest, except in three positively identified
    contexts: a URL, a path segment or call, and a Markdown code span.
    """
    context = context or _Context(value)
    window = max(0, at - 300)
    quoted = _QUOTED_LOCAL.search(value, window, at) or _ESCAPED_QUOTED_LOCAL.search(value, window, at)
    if quoted:
        return quoted.start()
    start, stop = at, max(floor, at - _LOCAL_PART_LIMIT)
    while start > stop and value[start - 1] in _ATEXT:
        start -= 1
    # Inside a URL the slash separates path segments, so it ends the local part: a path is no address, and an address
    # after a path segment starts after the slash.
    slash = value.rfind("/", start, at)
    if slash >= 0 and context.in_url(at):
        return slash + 1 if slash + 1 < at else None
    if start == floor > 0 and value[floor - 1] in _ATEXT:
        return floor
    # The nearest backtick string before the at sign that does not follow a letter or digit and that a backtick string of
    # equal length closes after it opens the code span that holds the at sign: those backticks are delimiters, and the
    # local part starts after them. A string that nothing closes there, or that the local part closes itself, is atext.
    limit = at
    while (mark := value.rfind("`", start, limit)) >= 0:
        first = mark
        while first > start and value[first - 1] == "`":
            first -= 1
        if first == start and start > 0 and value[start - 1] == "`":
            break  # the walk cut this string short, so its length is unknown
        if (first == 0 or not value[first - 1].isalnum()) and context.closes_after(mark + 1, mark + 1 - first, at):
            start = mark + 1
            break
        limit = first
    # An at sign right after a slash, with a name after it that a slash or an opening parenthesis follows, starts a path
    # segment or a call. The slash must be the character right before the at sign (no mailbox ends in one): a name or a
    # directory in front of the address leaves it whole, so legacy_credentials/NAME<at>HOST/adc.json masks together with
    # its directory prefix.
    if start < at and value[at - 1] == "/" and value[end:end + 1] in ("/", "("):
        return None
    return start if start < at else None


def _email_spans(value: str):
    floor, context = 0, _Context(value)
    for tail in _ADDRESS_TAIL.finditer(value):
        start = _local_start(value, tail.start(), tail.end(), floor, context)
        if start is not None:
            yield start, tail.end()
            floor = tail.end()


def _merged(spans) -> list[tuple[int, int]]:
    """Overlapping or touching spans as one, each from its minimum start, so no part of an outer local part survives."""
    merged: list[tuple[int, int]] = []
    for low, high in sorted(spans):
        if merged and low <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(high, merged[-1][1]))
        else:
            merged.append((low, high))
    return merged


def _mask_email(value: str) -> str:
    pieces, cursor = [], 0
    for start, end in _merged(_email_spans(value)):
        pieces += [value[cursor:start], _OMITTED]
        cursor = end
    return "".join(pieces) + value[cursor:]


@lru_cache(maxsize=65536)
def _decode_token(token: str) -> str:
    """Two rounds of percent, HTML-entity and backslash-escape decoding, as the token policy applies."""
    decoded = token
    for _ in range(2):
        decoded = unescape(unquote(decoded))
        decoded = re.sub(r"\\u([a-fA-F0-9]{4})|\\x([a-fA-F0-9]{2})", lambda match: chr(int(match.group(1) or match.group(2), 16)), decoded)
    return decoded


def _mask_decoded_email(value: str) -> str:
    """Omit every address the token-decoded text shows, exactly where decoding changed nothing, else whole tokens."""
    pieces, cursor = [], 0
    for match in _TOKEN.finditer(value):
        if match.start() > cursor:
            pieces.append((cursor, match.start(), value[cursor:match.start()], False))
        token = match.group()
        decoded_token = token if len(token) > 4096 else _decode_token(token)
        pieces.append((match.start(), match.end(), decoded_token, decoded_token != token))
        cursor = match.end()
    if cursor < len(value):
        pieces.append((cursor, len(value), value[cursor:], False))
    offsets, total = [], 0
    for piece in pieces:
        offsets.append(total)
        total += len(piece[2])
    decoded = "".join(piece[2] for piece in pieces)
    ranges = []
    for start, end in _email_spans(decoded):
        first, last = bisect_right(offsets, start) - 1, bisect_left(offsets, end) - 1
        low = pieces[first][0] if pieces[first][3] else pieces[first][0] + start - offsets[first]
        high = pieces[last][1] if pieces[last][3] else pieces[last][0] + end - offsets[last]
        ranges.append((low, high))
    out, cursor = [], 0
    for low, high in _merged(ranges):
        out += [value[cursor:low], _OMITTED]
        cursor = high
    return "".join(out) + value[cursor:]


def _private(value: str, identity) -> bool:
    return bool(_HOME.search(value) or _SESSION.search(value) or _TASK.search(value) or next(_email_spans(value), None) or is_account_url(value) or identity and identity.search(_without_preserved(value)))


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
    decoded = _decode_token(token)
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
    value = _mask_email(value)
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
        value = _mask_decoded_email(value)
        value = _TOKEN.sub(lambda match: _encoded_token(match.group(), identity), value)
        value = _portable_text(value, identity)
        return RESIDUE_OMITTED if _RESIDUE.search(value) else value
    if isinstance(value, dict):
        return {key: sanitize(child) for key, child in value.items()}
    if isinstance(value, list):
        return [sanitize(child) for child in value]
    return value


def text(value: Any) -> str:
    """Normalize a page label after applying the shared source projection."""
    return sanitize(str(sanitize(value) if value is not None else "Unspecified in source"))
