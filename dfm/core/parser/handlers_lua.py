"""Parser for Lua configs (Hyprland, Neovim, WezTerm, AwesomeWM, xplr)."""

import re

from dfm.core.parser.types import ConfigField, FieldType
from dfm.core.parser.infer import make_display_name


# key = value, where key is an identifier (rounding), a dotted path
# (vim.opt.number) or a bracketed literal (["col.active_border"])
ASSIGNMENT = re.compile(
    r"^(?:local\s+)?"
    r"(?P<key>[A-Za-z_][\w.]*|\[\s*(?P<q>[\"'])(?P<bracket_key>[^\"']*)(?P=q)\s*\])"
    r"\s*=\s*(?P<value>.*)$"
)
BANNER = re.compile(r"^[-=*~#]{3,}")
LONG_STRING = re.compile(r"^\[(=*)\[(.*)\]\1\]$", re.DOTALL)
BLOCK_OPEN = re.compile(r"\b(function|if|do)\b")
BLOCK_CLOSE = re.compile(r"\bend\b")
STRING_LITERAL = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")


class _Scope:
    """One open table constructor while walking the file."""

    def __init__(self, name: str | None) -> None:
        self.name = name
        self.items = 0


class _LuaState:
    """Parser state carried across lines."""

    def __init__(self) -> None:
        self.scopes: list[_Scope] = []
        self.comment_buffer = ""
        self.banner_section = "General"
        self.in_block_comment = False
        self.block_depth = 0


def parse_lua(content: str) -> list[ConfigField]:
    """Parse a Lua config file into editable fields."""
    fields: list[ConfigField] = []
    state = _LuaState()

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        if state.in_block_comment:
            if "]]" in stripped:
                state.in_block_comment = False
            continue

        if not stripped:
            state.comment_buffer = ""
            continue

        code, comment = split_lua_comment(stripped)
        code = code.strip()

        if not code:
            _handle_comment_line(fields, state, comment, line, line_num)
            continue

        if _track_block(state, code):
            state.comment_buffer = ""
            continue

        _handle_code_line(fields, state, code, comment, line, line_num)

    return fields


def split_lua_comment(text: str) -> tuple[str, str]:
    """Split a Lua line into (code, comment); their concatenation is `text`."""
    quote: str | None = None
    i = 0
    while i < len(text):
        char = text[i]
        if quote:
            if char == "\\":
                i += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "-" and text.startswith("--", i):
            return text[:i], text[i:]
        i += 1
    return text, ""


def _track_block(state: _LuaState, code: str) -> bool:
    """Follow function/if/do blocks; return True while inside one.

    Statements inside a block are executable code rather than settings, so
    they are not turned into editable fields.
    """
    bare = STRING_LITERAL.sub('""', code)
    delta = len(BLOCK_OPEN.findall(bare)) - len(BLOCK_CLOSE.findall(bare))

    if state.block_depth > 0:
        state.block_depth = max(0, state.block_depth + delta)
        return True

    if delta > 0:
        state.block_depth = delta
        return True

    return False


def _handle_comment_line(fields: list[ConfigField], state: _LuaState,
                         comment: str, line: str, line_num: int) -> None:
    """Handle a line that holds nothing but a comment."""
    inner = comment.lstrip("-").strip()

    if inner.startswith("[[") and "]]" not in inner:
        state.in_block_comment = True
        state.comment_buffer = ""
        return

    if state.scopes:
        # Inside a table a comment describes the next entry, never a section.
        state.comment_buffer = inner
        return

    name = _banner_section(inner)
    if name is None:
        state.comment_buffer = inner
        return

    state.banner_section = name
    state.comment_buffer = ""
    fields.append(ConfigField(
        key=name,
        display_name=name,
        value="",
        field_type=FieldType.COMMENT,
        section=name,
        line_number=line_num,
        original_line=line,
    ))


def _banner_section(inner: str) -> str | None:
    """Return a section name if the comment looks like a banner header."""
    name = inner.strip("-=*~# ").strip()
    if len(name) < 3:
        return None
    if BANNER.match(inner) or inner.isupper():
        return name.title()
    return None


def _handle_code_line(fields: list[ConfigField], state: _LuaState, code: str,
                      comment: str, line: str, line_num: int) -> None:
    """Handle a line holding Lua code."""
    if code.startswith(("}", ")")):
        for char in code:
            if char == "}" and state.scopes:
                state.scopes.pop()
        state.comment_buffer = ""
        return

    match = ASSIGNMENT.match(code)
    if match is None:
        _handle_keyless_line(fields, state, code, line, line_num)
        state.comment_buffer = ""
        return

    key = match.group("bracket_key") or match.group("key")
    value = _strip_separators(match.group("value"))

    if _opens_table(value):
        state.scopes.append(_Scope(key))
        path = _path(state.scopes)
        fields.append(ConfigField(
            key=path,
            display_name=make_display_name(key),
            value="",
            field_type=FieldType.COMMENT,
            section=path,
            comment=state.comment_buffer,
            line_number=line_num,
            original_line=line,
        ))
    elif _is_editable(value):
        fields.append(ConfigField(
            key=_path(state.scopes, key),
            display_name=make_display_name(key),
            value=_unquote(value),
            field_type=FieldType.TEXT,
            section=_current_section(state),
            comment=state.comment_buffer or comment.lstrip("-").strip(),
            line_number=line_num,
            original_line=line,
        ))

    state.comment_buffer = ""


def _handle_keyless_line(fields: list[ConfigField], state: _LuaState,
                         code: str, line: str, line_num: int) -> None:
    """Handle table entries with no key: array items and nested constructors."""
    if code.endswith("{"):
        if code == "{" and state.scopes:
            parent = state.scopes[-1]
            parent.items += 1
            state.scopes.append(_Scope(f"[{parent.items}]"))
        else:
            # `return {`, `foo({`, or the opening line of a top-level table.
            state.scopes.append(_Scope(None))
        return

    if not state.scopes:
        return

    value = _strip_separators(code)
    if not is_literal(value) or not _is_editable(value):
        return

    parent = state.scopes[-1]
    parent.items += 1
    index = f"[{parent.items}]"

    fields.append(ConfigField(
        key=_path(state.scopes) + index,
        display_name=f"Item {parent.items}",
        value=_unquote(value),
        field_type=FieldType.TEXT,
        section=_current_section(state),
        comment=state.comment_buffer,
        line_number=line_num,
        original_line=line,
    ))


def _opens_table(value: str) -> bool:
    """True when the value is a table constructor left open on this line."""
    if not value.startswith("{"):
        return False
    code, _ = split_lua_comment(value)
    return code.count("{") > code.count("}")


def is_literal(value: str) -> bool:
    """True when the text is a literal (string, number, table, boolean, nil)."""
    if not value:
        return False
    if value[0] in "\"'{[" or value[0].isdigit() or value[0] == "-":
        return True
    return value in ("true", "false", "nil")


def _is_editable(value: str) -> bool:
    """Only plain literals and table snippets are safe to edit as values."""
    if not value or value.startswith("require"):
        return False
    stripped = STRING_LITERAL.sub('""', value)
    return "(" not in stripped


def _strip_separators(value: str) -> str:
    """Drop the trailing comma/semicolon that separates table entries."""
    return value.strip().rstrip(",;").strip()


def _unquote(value: str) -> str:
    """Return the display form of a Lua literal."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace("\\" + value[0], value[0]).replace("\\\\", "\\")
    match = LONG_STRING.match(value)
    if match:
        return match.group(2)
    return value


def _path(scopes: list[_Scope], key: str | None = None) -> str:
    """Build the dotted path of the current scope, optionally plus a key."""
    parts = [s.name for s in scopes if s.name]
    if key:
        parts.append(key)

    path = ""
    for part in parts:
        if part.startswith("["):
            path += part
        elif path:
            path += f".{part}"
        else:
            path = part
    return path


def _current_section(state: _LuaState) -> str:
    """Section a field belongs to: its table path, or the last banner."""
    return _path(state.scopes) or state.banner_section
