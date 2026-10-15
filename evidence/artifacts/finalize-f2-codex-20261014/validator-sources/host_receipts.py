# Verbatim selected definitions: native-agent-stack@252babe4040e39173cc178317c67699371806df6 scripts/host_receipts.py

GITHUB_REPOSITORY_PATTERN = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([^/\s#?]+)/([^/\s#?]+)", re.IGNORECASE)

def normalize_repository(value) -> str | None:
    """Comparable form of a repository URL, lower-cased with surrounding whitespace removed.

    A GitHub URL reduces to ``github.com/<owner>/<repo>``: the scheme, a ``www.`` prefix, a trailing
    ``.git`` and every path segment after owner/repo (``/releases/tag/v1``, ``/tree/v1``, ``/blob/...``,
    a trailing ``/``) are dropped, the same owner/repo form as
    ``tools/sota-convergence/build_manifest.py``'s ``github_repo_slug`` (manifests/stack.json records
    some repositories as release or tree URLs). Any other URL keeps its path and only loses the
    scheme, a ``www.`` prefix, trailing ``/`` and trailing ``.git``, since other forges nest groups.
    ``None`` for a non-string or empty value, which never matches."""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    match = GITHUB_REPOSITORY_PATTERN.match(text)
    if match:
        owner, repository = match.group(1), match.group(2)
        repository = repository[:-len(".git")] if repository.endswith(".git") else repository
        return f"github.com/{owner}/{repository}" if repository else None
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text[len("www."):] if text.startswith("www.") else text
    previous = None
    while text != previous:
        previous = text
        text = text.rstrip("/")
        text = text[:-len(".git")] if text.endswith(".git") else text
    return text or None
