"""Analyzer checks specific to Lua configs."""

import os
import re

from dfm.core.analyzer_types import FileAnalysis, Issue, IssueSeverity
from dfm.core.parser.handlers_lua import parse_lua, split_lua_comment
from dfm.core.parser.types import FieldType


_REQUIRE = re.compile(r"""(?:require|dofile|loadfile)\s*\(?\s*["']([\w.\-/]+)["']""")


def is_lua(file_path: str) -> bool:
    """True for Lua configs (Hyprland, Neovim, WezTerm, AwesomeWM, …)."""
    return os.path.splitext(file_path)[1].lower() == ".lua"


def check_lua_requires(fa: FileAnalysis, lines: list[str],
                       file_path: str) -> None:
    """Check that Lua modules required from this config actually exist.

    Modules installed by plugin managers live outside the config tree, so only
    namespaces that clearly belong to this config are reported.
    """
    base_dir = os.path.dirname(file_path)
    roots = [os.path.join(base_dir, "lua"), base_dir]

    for i, line in enumerate(lines, 1):
        code, _ = split_lua_comment(line.strip())
        for match in _REQUIRE.finditer(code):
            module = match.group(1)
            rel = module.replace(".", os.sep).replace("/", os.sep)

            if any(os.path.isfile(os.path.join(root, rel + ".lua")) or
                   os.path.isfile(os.path.join(root, rel, "init.lua"))
                   for root in roots):
                continue

            namespace = rel.split(os.sep)[0]
            if namespace == rel:
                continue  # single-name module: almost always a plugin
            if not any(os.path.isdir(os.path.join(root, namespace))
                       for root in roots):
                continue

            fa.issues.append(Issue(
                severity=IssueSeverity.WARNING,
                title="Missing Lua module",
                detail=f"Line {i}: require('{module}') — no matching "
                       f"{rel}.lua or {rel}/init.lua",
                file_path=file_path,
                line_number=i,
                category="reference",
                fix_hint=f"Create lua/{rel}.lua or fix the module name",
            ))


def check_lua_duplicate_keys(fa: FileAnalysis, lines: list[str],
                             file_path: str) -> None:
    """Detect table keys assigned twice within the same Lua table."""
    seen_keys: dict[str, list[int]] = {}

    for field_obj in parse_lua("\n".join(lines)):
        if field_obj.field_type == FieldType.COMMENT:
            continue
        seen_keys.setdefault(field_obj.key, []).append(field_obj.line_number)

    for key, line_numbers in seen_keys.items():
        if len(line_numbers) < 2:
            continue
        lines_str = ", ".join(str(n) for n in line_numbers)
        fa.issues.append(Issue(
            severity=IssueSeverity.WARNING,
            title="Duplicate key",
            detail=f"'{key}' assigned {len(line_numbers)} times "
                   f"(lines {lines_str}) — later value wins",
            file_path=file_path,
            line_number=line_numbers[-1],
            category="duplicate",
        ))
