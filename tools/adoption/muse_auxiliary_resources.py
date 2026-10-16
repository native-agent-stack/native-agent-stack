"""Admit the named public dependencies of the OpenCode Muse TRIAL profile.

This is an inventory of existing installations, not an installer or a fallback
search. The package pins come from the installed public package manifests:
RTK 0.51.0 (rtk-ai/rtk@e001f773), Serena's direct_url.json at
oraios/serena@c6fbd1c5932df2494ffa0020af5a9fbe80b82143, Semble 0.6.2,
jcodemunch-mcp 1.108.333, SocratiCode 1.15.0 and promptfoo 0.124.0.

npm 11.19.0 bin/npx-cli.js:3-7 resolves ../lib/cli.js and npm-cli.js;
executing its physical module path preserves that vendor-relative lookup.
CPython's virtual-environment mechanism uses pyvenv.cfg and site-packages;
each installed console script also names its own bin/python in its shebang.
Serena's pinned src/serena/config/serena_config.py:65-78 supports SERENA_HOME;
Semble 0.6.2 semble/cache.py:63-88 supports SEMBLE_CACHE_LOCATION/XDG.

Only exact public files/package-resource roots are returned. Caller-owned
native authentication, cache and session directories are never inputs.
"""

from __future__ import annotations

from email.parser import Parser
import json
import os
from pathlib import Path
import shutil
from typing import Mapping, Sequence


class AuxiliaryResourceError(ValueError):
    """A required public dependency differs from the reviewed inventory."""


SERENA_COMMIT = "c6fbd1c5932df2494ffa0020af5a9fbe80b82143"
PINS = {
    "rtk": "0.51.0", "node": "24.21.0", "python": "3.13.16", "npm": "11.19.0",
    "serena-agent": "2.0.0.dev0", "semble": "0.6.2", "jcodemunch-mcp": "1.108.333",
    "socraticode": "1.15.0", "promptfoo": "0.124.0",
}


def _file(path: Path, label: str, *, executable: bool = False) -> Path:
    if not path.is_file() or (executable and not os.access(path, os.X_OK)):
        raise AuxiliaryResourceError(f"{label} required file unavailable")
    return path


def _directory(path: Path, label: str) -> Path:
    if not path.is_dir() or path.absolute() != path.resolve():
        raise AuxiliaryResourceError(f"{label} required public directory unavailable")
    return path


def _json(path: Path, label: str) -> dict:
    try:
        value = json.loads(_file(path, label).read_text())
    except (OSError, ValueError) as error:
        raise AuxiliaryResourceError(f"{label} package metadata unavailable") from error
    if not isinstance(value, dict):
        raise AuxiliaryResourceError(f"{label} package metadata differs")
    return value


def _node_package(root: Path, name: str, entrypoint: str) -> Path:
    _directory(root, name)
    metadata = _json(root / "package.json", name)
    if metadata.get("name") != name or metadata.get("version") != PINS[name]:
        raise AuxiliaryResourceError(f"{name} installed package pin differs")
    _directory(root / "node_modules", name + " dependencies")
    return _file(root / entrypoint, name + " entrypoint", executable=True)


def _venv(root: Path, command: str, package: str, python_root: Path) -> list[Path]:
    cfg = _file(root / "pyvenv.cfg", command + " virtual environment")
    values = dict(line.split("=", 1) for line in cfg.read_text().splitlines() if "=" in line)
    values = {key.strip(): value.strip() for key, value in values.items()}
    if (values.get("version_info") != PINS["python"]
            or values.get("home") != str(python_root / "bin")
            or values.get("include-system-site-packages") != "false"):
        raise AuxiliaryResourceError(f"{command} virtual environment interpreter differs")
    site = _directory(root / "lib/python3.13/site-packages", command + " dependencies")
    matches = list(site.glob(package.replace("-", "_") + "-*.dist-info"))
    if len(matches) != 1:
        raise AuxiliaryResourceError(f"{command} installed package pin unavailable")
    metadata = Parser().parsestr(_file(matches[0] / "METADATA", command).read_text())
    if metadata.get("Name") != package or metadata.get("Version") != PINS[package]:
        raise AuxiliaryResourceError(f"{command} installed package pin differs")
    if command == "serena":
        provenance = _json(matches[0] / "direct_url.json", command)
        if (provenance.get("url", "").rstrip("/") != "https://github.com/oraios/serena"
                or provenance.get("vcs_info", {}).get("commit_id") != SERENA_COMMIT):
            raise AuxiliaryResourceError("serena installed source pin differs")
    interpreter = _file(root / "bin/python", command + " interpreter", executable=True)
    if interpreter.resolve() != python_root / "bin/python3.13":
        raise AuxiliaryResourceError(f"{command} interpreter target differs")
    entrypoint = _file(root / "bin" / command, command + " entrypoint", executable=True)
    with entrypoint.open("rb") as handle:
        shebang = handle.readline(4096).rstrip(b"\r\n")
    if shebang != ("#!" + str(interpreter)).encode():
        raise AuxiliaryResourceError(f"{command} entrypoint interpreter differs")
    return [cfg, site, interpreter, entrypoint]


def qualify_auxiliary_resources(
    *, home: Path, eco_root: Path, profile_root: Path,
    local_commands: Mapping[str, Sequence[str]] | None = None,
    executables: Mapping[str, Path] | None = None,
) -> dict:
    """Return reviewed RO resources, physical MCP commands and private state env.

    ``local_commands`` contains the canonical renderer's local-server argv.
    Only the six named servers are rewritten; their argument tails are kept.
    The optional executable map is a dependency-injection seam for fixtures;
    selected files must still resolve to the same fixed reviewed locations.
    This function neither executes a command nor creates state directories.
    """
    home, eco_root, profile_root = (Path(p).absolute() for p in (home, eco_root, profile_root))
    node_root = home / ".local/share/mise/installs/node" / PINS["node"]
    python_root = home / ".local/share/mise/installs/python" / PINS["python"]
    _file(node_root / "bin/node", "node", executable=True)
    _file(python_root / "bin/python3.13", "python", executable=True)
    paths = {_directory(python_root / "lib", "python libraries")}

    npm = node_root / "lib/node_modules/npm"
    socraticode = eco_root / "tools/socraticode-1.15.0/lib/node_modules/socraticode"
    promptfoo = eco_root / "tools/promptfoo-0.124.0/lib/node_modules/promptfoo"
    npx_file = _node_package(npm, "npm", "bin/npx-cli.js")
    socraticode_file = _node_package(socraticode, "socraticode", "dist/index.js")
    promptfoo_file = _node_package(promptfoo, "promptfoo", "dist/src/entrypoint.js")
    paths.update([npm, socraticode, promptfoo])
    venv_roots = {
        "serena": (home / ".local/share/uv/tools/serena-agent", "serena-agent"),
        "semble": (home / ".local/share/uv/tools/semble", "semble"),
        "jcodemunch-mcp": (eco_root / "python-tools/jcodemunch-mcp", "jcodemunch-mcp"),
    }
    for command, (root, package) in venv_roots.items():
        paths.update(_venv(root, command, package, python_root))
    targets = {
        "node": node_root / "bin/node", "npx": npx_file,
        "rtk": eco_root / "tools/rtk-0.51.0/rtk", "promptfoo": promptfoo_file,
        **{name: root / "bin" / name for name, (root, _) in venv_roots.items()},
    }
    selected = {}
    for name, target in targets.items():
        choice = executables.get(name) if executables is not None else shutil.which(name)
        if not choice:
            raise AuxiliaryResourceError(f"{name} selected entrypoint unavailable")
        alias = _file(Path(choice).absolute(), name + " selected entrypoint", executable=True)
        _file(target, name + " physical entrypoint", executable=True)
        if alias.resolve() != target:
            raise AuxiliaryResourceError(f"{name} selected entrypoint differs from reviewed installation")
        selected[name] = alias
        paths.update([alias, target])
    paths.update([python_root / "bin/python3.13"])
    for path in paths:
        if path.is_dir() and (profile_root == path or profile_root.is_relative_to(path)):
            raise AuxiliaryResourceError("profile state overlaps a public dependency directory")

    rewritten = {}
    source_names = {"serena": "serena", "semble": "semble", "jcodemunch": "jcodemunch-mcp",
                    "chrome-devtools": "npx", "promptfoo": "promptfoo", "socraticode": "node"}
    for server, name in source_names.items():
        if local_commands is None or server not in local_commands:
            continue
        argv = list(local_commands[server])
        allowed = {name, str(selected[name]), str(targets[name])}
        if not argv or argv[0] not in allowed:
            raise AuxiliaryResourceError(f"{server} canonical command differs")
        if server == "socraticode":
            if len(argv) < 2 or argv[1] != str(socraticode_file):
                raise AuxiliaryResourceError("socraticode canonical command differs")
            rewritten[server] = [str(targets["node"]), *argv[1:]]
        elif name in {"npx", "promptfoo"}:
            rewritten[server] = [str(targets["node"]), str(targets[name]), *argv[1:]]
        else:
            rewritten[server] = [str(targets[name]), *argv[1:]]
    return {
        "qualified_auxiliary_read_paths": sorted(map(str, paths)),
        "local_server_commands": rewritten,
        "environment": {"SERENA_HOME": str(profile_root / "serena"),
                        "npm_config_cache": str(profile_root / "npm-cache"),
                        "SEMBLE_CACHE_LOCATION": str(profile_root / "semble-cache"),
                        "PYTHONDONTWRITEBYTECODE": "1"},
        "pins": {**PINS, "serena_commit": SERENA_COMMIT},
    }
