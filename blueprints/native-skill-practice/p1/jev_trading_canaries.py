"""Decision 7 date-shift reference recipe and exact fixed-n audit.

The date expression is verbatim JV47, sha256 4c708d21... . The rule is the
2026-10-11 decision's specified +728-day transformation, not a date parser
substitution. Mask recognition/auditor selection remain separately frozen inputs.
"""
from __future__ import annotations

from datetime import date, timedelta
import re

from scipy import stats

from jev_trading_cases import CaseSet, id_hash, sha256

DATE_PATTERN = r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(?:[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?(?![\d.,%])\b|\b(?:[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b|\b(?:19|20)\d{2}-[01]\d-[0-3]\d\b|\b[0-3]?\d[/.][01]?\d[/.](?:19|20)\d{2}\b"
DATE_REGEX = re.compile(DATE_PATTERN)
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
DATE_ID_PINS = {"FPB-50": "e1ec893251c2272482a5a5431b9b9425478d32dff2dda07dab1a89efc4c530a0",
                "TFN": "620cb349447fd38b32cc63d5502acac01f71757d152a7e2cc63ad9ed26d00797"}


def _ordinal(day: int) -> str:
    return "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _rewrite(text: str, match) -> tuple[str, int, bool]:
    raw = match.group()
    end = match.end()
    if raw[0].isdigit() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        moved = date.fromisoformat(raw) + timedelta(days=728)
        return moved.isoformat(), end, False
    if re.fullmatch(r"[\d/.]+", raw):
        pieces = re.split(r"([/.])", raw)
        a, sep, b, other, year = pieces
        if sep != other:
            raise ValueError("mixed separators")
        day, month = (int(a), int(b)) if sep == "." else (int(b), int(a))
        moved = date(int(year), month, day) + timedelta(days=728)
        values = (moved.day, moved.month) if sep == "." else (moved.month, moved.day)
        fields = [str(value).zfill(2) if len(original) == 2 else str(value)
                  for value, original in zip(values, (a, b))]
        return sep.join([*fields, str(moved.year)]), end, False
    month_first = raw[0].isalpha()
    month_text = re.findall(r"[A-Za-z]+", raw)[0 if month_first else -1]
    month = next(i for i, name in enumerate(MONTHS, 1) if name.lower().startswith(month_text[:3].lower()))
    abbreviated = len(month_text) < len(MONTHS[month - 1])
    period = "." in raw
    if not month_first and abbreviated and text[end:end + 1] == ".":
        period = True
        end += 1
    number = re.search(r"(\d+)(st|nd|rd|th)?", raw, re.IGNORECASE)
    day, suffix = int(number[1]), bool(number[2])
    range_match = re.match(r"(\s*(?:-|–|to)\s*)(\d{1,2})(st|nd|rd|th)?\b", text[end:], re.IGNORECASE)
    if range_match:
        end += range_match.end()
    year_match = re.match(r"(\s*,\s*|\s+)((?:19|20)\d{2})\b", text[end:])
    year = int(year_match[2]) if year_match else 2001
    year_separator = year_match[1] if year_match else ""
    if year_match:
        end += year_match.end()
    first = date(year, month, day) + timedelta(days=728)
    last = date(year, month, int(range_match[2])) + timedelta(days=728) if range_match else None
    def render(value, ordinal, include_month=True, include_year=False):
        name = MONTHS[value.month - 1][:3] if abbreviated else MONTHS[value.month - 1]
        name += "." if period else ""
        day_string = str(value.day) + (_ordinal(value.day) if ordinal else "")
        rendered = (name + " " + day_string if month_first else day_string + " " + name) if include_month else day_string
        return rendered + (year_separator + str(value.year) if include_year else "")
    if last is None:
        return render(first, suffix, include_year=bool(year_match)), end, False
    different_year = first.year != last.year and bool(year_match)
    result = render(first, suffix, include_year=different_year)
    result += range_match[1] + render(last, bool(range_match[3]),
        include_month=first.month != last.month or different_year, include_year=bool(year_match))
    return result, end, False


def shift_dates(text: str) -> dict:
    pieces = []
    rewritten_ends = []
    cursor = matched = shifted = unchanged = guarded = 0
    for match in DATE_REGEX.finditer(text):
        if match.start() < cursor:
            continue
        if re.search(r"\$[A-Za-z][A-Za-z.]{0,9}\s+$", text[:match.start()]) and re.match(r"\s+[PC]\b", text[match.end():]):
            continue
        matched += 1
        try:
            replacement, end, leftover = _rewrite(text, match)
        except (ValueError, OverflowError):
            unchanged += 1
            continue
        if leftover:
            guarded += 1
            unchanged += 1
            continue
        # Guard the actual consumed span, including numeric dates.
        if re.match(r"\W{0,4}(?:19|20)\d{2}\b", text[end:]):
            guarded += 1
            unchanged += 1
            continue
        pieces.extend((text[cursor:match.start()], replacement))
        rewritten_ends.append(sum(map(len, pieces)))
        cursor = end
        shifted += 1
    pieces.append(text[cursor:])
    result = "".join(pieces)
    return {"text": result, "matches": matched, "shifted": shifted, "unchanged": unchanged,
            "guarded_years": guarded,
            "leftover_years": sum(bool(re.match(r"\W{0,4}(?:19|20)\d{2}\b", result[end:])) for end in rewritten_ends)}


def freeze_dates(pack: CaseSet, *, frozen: bool) -> dict:
    changed = {r.id: shift_dates(r.text) for r in pack.scored}
    selected = {i: value for i, value in changed.items() if value["matches"]}
    digest = id_hash(selected)
    if frozen and pack.name in DATE_ID_PINS and digest != DATE_ID_PINS[pack.name]:
        raise ValueError("date subset id-list pin mismatch")
    if frozen and pack.name == "FOMC" and selected:
        raise ValueError("FOMC date subset must be empty")
    if any(row["leftover_years"] for row in selected.values()):
        raise ValueError("shift left a year behind")
    return {"ids": sorted(selected), "id_sha256": digest, "expression_sha256": sha256(DATE_PATTERN.encode()),
            "shifted_matches": sum(r["shifted"] for r in selected.values()),
            "unchanged_matches": sum(r["unchanged"] for r in selected.values()),
            "guarded_years": sum(r["guarded_years"] for r in selected.values()), "leftover_years": 0}


def audit_result(recovered: list[bool | None]) -> dict:
    """Invalid/missing auditor answer counts as recovery; no replacement draw."""
    n = len(recovered)
    if n != 281:
        return {"status": "NO_VERDICT", "n": n, "required_n": 281, "k": 10}
    count = sum(value is not False for value in recovered)
    upper = float(stats.binomtest(count, n, alternative="less").proportion_ci(
        confidence_level=0.95, method="exact").high)
    return {"status": "PASS" if upper < 0.15 else "FAIL", "n": n, "recoveries": count,
            "upper_95": upper, "margin": 0.15, "k": 10}
