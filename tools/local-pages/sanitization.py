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
(the slash must be the character right before the at sign, so an address that is
itself a path segment, such as gcloud's legacy_credentials/NAME<at>HOST/adc.json,
masks whole with its directory prefix; RFC 5322 also allows a local part that ends
in a slash, and such an address with a slash or a parenthesis after it stays
readable, a cost #1012's Follow-ups record); and a backtick string that a backtick
string of equal length closes after the at sign opens a Markdown code span
(CommonMark 0.31.2 section 6.1) when it does not follow a letter or digit, a
condition of this mask that CommonMark does not set and that masks more, so
`@AGENTS.md` is not an address and a code span
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
A token over 4,096 characters is not decoded for the mask, so the mask first
matches these encoded forms in place, as the b209afe8 page-local mask did for %40
and &#64;: for the at sign %40, %2540, &#64 and &#x40 (each reference with or
without its semicolon) and &commat;, for the dot %2E, %252E, &#46, &#x2E and
&period;, and for the quotes of a quoted local part ", %22, %2522, &quot, &#34 and
&#x22 (each reference with or without its semicolon). No such token is published
unchecked (#1012 GPT fix3 verdict, BLOCKER 2): it is then decoded with the same
two rounds, and one that an address touches in its decoded text, or whose decoded
text turns the character beside an in-place mask into part of the address, is
omitted whole as "[email omitted]"; one whose decoded text, or the text it encodes
as hex or base64, holds a home path, a session id, a task handle, an account URL
or the home name reads LONG_TOKEN_OMITTED. A name ending in one of ten systemd unit types (systemd.unit(5):
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
LONG_TOKEN_OMITTED = "[long token omitted: it decodes to private text]"
# Tokens longer than this are masked in place rather than decoded for the mask (the cost bound); each is still decoded
# and checked before it is published.
_DECODE_LIMIT = 4096
_ESCAPE = re.compile(r"\\u([a-fA-F0-9]{4})|\\x([a-fA-F0-9]{2})")
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
_PRESERVED = re.compile(r"\$\{(?:USER_HOME|LOCAL_SESSION_ID|LOCAL_TASK_HANDLE)\}|\[personal identifier omitted\]|\[account artifact omitted\]|\[email omitted\]|\[value omitted: an at sign beside a word remained after masking\]|\[long token omitted: it decodes to private text\]|native-agent-stack-1a")
# The two halves of the placeholder, split by its space, and what may stand beside a mask in a decoded long token: a
# local-part character (atext or the quote of a quoted string) before it, a domain character after it.
_MASK_HEAD, _MASK_TAIL = _OMITTED.split(" ")
_LOCAL_END = frozenset(_ATEXT | {'"'})
_DOMAIN_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.")


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
    # The nearest backtick string before the at sign that a backtick string of equal length closes after it (CommonMark
    # 0.31.2 section 6.1) opens the code span that holds the at sign, when it does not follow a letter or digit (this
    # mask's own condition, stricter than CommonMark): those backticks are delimiters, and the local part starts after
    # them. A string that nothing closes there, or that the local part closes itself, is atext.
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
    # segment or a call. The slash must be the character right before the at sign: a name or a directory in front of the
    # address leaves it whole, so legacy_credentials/NAME<at>HOST/adc.json masks together with its directory prefix.
    # RFC 5322 also allows a local part that ends in a slash; such an address in this position stays readable, a cost
    # #1012's Follow-ups record.
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


def _omit(value: str, spans) -> str:
    pieces, cursor = [], 0
    for start, end in _merged(spans):
        pieces += [value[cursor:start], _OMITTED]
        cursor = end
    return "".join(pieces) + value[cursor:]


def _mask_email(value: str) -> str:
    return _omit(value, _email_spans(value))


def _decode_text(value: str) -> str:
    """Two rounds of percent, HTML-entity and backslash-escape decoding, as the token policy applies."""
    for _ in range(2):
        value = _ESCAPE.sub(lambda match: chr(int(match.group(1) or match.group(2), 16)), unescape(unquote(value)))
    return value


@lru_cache(maxsize=65536)
def _decode_token(token: str) -> str:
    """_decode_text for a token within the decoding bound, cached: the same tokens recur across a page."""
    return _decode_text(token)


def _pieces(value: str, long_tokens: bool) -> list[tuple[int, int, str, bool]]:
    """The text as (start, end, decoded text, changed) pieces, each token decoded; a token over the bound only when asked."""
    pieces, cursor = [], 0
    for match in _TOKEN.finditer(value):
        if match.start() > cursor:
            pieces.append((cursor, match.start(), value[cursor:match.start()], False))
        token = match.group()
        decoded = _decode_token(token) if len(token) <= _DECODE_LIMIT else _decode_text(token) if long_tokens else token
        pieces.append((match.start(), match.end(), decoded, decoded != token))
        cursor = match.end()
    if cursor < len(value):
        pieces.append((cursor, len(value), value[cursor:], False))
    return pieces


def _decoded_spans(value: str, pieces) -> list[tuple[int, int]]:
    """Where each address the decoded pieces show lies in value: exactly where decoding changed nothing, else whole pieces."""
    offsets, total = [], 0
    for piece in pieces:
        offsets.append(total)
        total += len(piece[2])
    decoded = "".join(piece[2] for piece in pieces)
    spans = []
    for start, end in _email_spans(decoded):
        first, last = bisect_right(offsets, start) - 1, bisect_left(offsets, end) - 1
        low = pieces[first][0] if pieces[first][3] else pieces[first][0] + start - offsets[first]
        high = pieces[last][1] if pieces[last][3] else pieces[last][0] + end - offsets[last]
        spans.append((low, high))
    return spans


def _joins_mask(value: str, start: int, end: int) -> tuple[int, int] | None:
    """The span to omit when decoding the token value[start:end] turns the character beside its mask into address text.

    An in-place mask stops its walk back at the first character that is not atext and its domain at the first that is no
    domain character. Where decoding makes that character a local-part or a domain character, part of the address would
    read once decoded, so the token is omitted whole together with the placeholder it touches."""
    token = value[start:end]
    before = token[:-len(_MASK_HEAD)] if token.endswith(_MASK_HEAD) and value.startswith(" " + _MASK_TAIL, end) else ""
    after = token[len(_MASK_TAIL):] if token.startswith(_MASK_TAIL) and value.endswith(_MASK_HEAD + " ", 0, start) else ""
    if before and before[-1] not in _ATEXT and _decode_text(before)[-1:] in _LOCAL_END:
        return start, end + len(_MASK_TAIL) + 1
    if after and after[0] not in _DOMAIN_CHARS and _decode_text(after)[:1] in _DOMAIN_CHARS:
        return start - len(_MASK_HEAD) - 1, end
    return None


def _mask_decoded_email(value: str) -> str:
    """Omit every address the token-decoded text shows, exactly where decoding changed nothing, else whole tokens.

    A token over the decoding bound is masked in place first. When the text has one, the masked text is read again with
    every token decoded: a token that an address touches there, or that _joins_mask flags, is omitted whole, so no long
    token reaches a page unchecked."""
    pieces = _pieces(value, long_tokens=False)
    masked = _omit(value, _decoded_spans(value, pieces))
    if all(end - start <= _DECODE_LIMIT for start, end, _, _ in pieces):
        return masked
    pieces = _pieces(masked, long_tokens=True)
    spans = _decoded_spans(masked, pieces) + [span for start, end, _, _ in pieces if (span := _joins_mask(masked, start, end))]
    return _omit(masked, spans) if spans else masked


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


def _candidate(token: str) -> str | None:
    """The UTF-8 text a token of at least 12 characters encodes as hex or base64, if it is one."""
    try:
        if len(token) >= 12 and len(token) % 2 == 0 and re.fullmatch(r"[a-fA-F0-9]+", token):
            return bytes.fromhex(token).decode("utf-8")
        if len(token) >= 12 and re.fullmatch(r"[A-Za-z0-9_+/-]+={0,2}", token):
            return base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True).decode("utf-8")
    except (ValueError, UnicodeError, binascii.Error):
        pass
    return None


def _encoded_token(token: str, identity) -> str:
    """Omit an encoded token only when its decoded text matches the policy."""
    if len(token) > _DECODE_LIMIT:
        # Masked in place, never published unchecked: a long token whose decoded text, after the in-place projection, or
        # whose hex or base64 text is private is omitted whole (#1012 GPT fix3 verdict, BLOCKER 2).
        projected = _portable_text(token, identity)
        decoded = _decode_text(projected)
        candidate = _candidate(token)
        private = decoded != projected and _private(decoded, identity) or candidate is not None and _private(candidate, identity)
        return LONG_TOKEN_OMITTED if private else token
    decoded = _decode_token(token)
    if decoded != token and _private(decoded, identity):
        return _portable_text(decoded, identity)
    candidate = _candidate(token)
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


# A run of 7 to 64 hex characters that no other letter or digit touches: a digest, or a prefix of one in a name.
_HEX_RUN = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{7,64}(?![0-9A-Za-z])")
DIGEST_PREFIX_WITHHELD = "[digest prefix withheld]"


def withhold_digests(markup: str, digests, note: str) -> str:
    """Rendered text with no private digest and no prefix of one 7 or more characters long (#161).

    `digests` are the SHA-256 hex digests of private bytes. A whole digest reads `note`, and a shorter prefix, such as
    the first 16 hex characters in a content-addressed file name, reads DIGEST_PREFIX_WITHHELD."""
    prefixes = {digest.lower()[:length] for digest in digests if isinstance(digest, str) for length in range(7, 65)}
    if not prefixes:
        return markup
    return _HEX_RUN.sub(lambda match: (note if len(match.group()) == 64 else DIGEST_PREFIX_WITHHELD) if match.group().lower() in prefixes else match.group(), markup)
