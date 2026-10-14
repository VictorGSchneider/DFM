"""Update individual config values on disk while preserving formatting."""

import json
import os
import re
import shutil
import tempfile

from dfm.core.parser.types import ConfigField, FieldType, BOOL_TRUE, BOOL_FALSE
from dfm.core.parser.detect import detect_format
from dfm.core.parser.handlers_lua import ASSIGNMENT as LUA_ASSIGNMENT
from dfm.core.parser.handlers_lua import LONG_STRING, is_literal, split_lua_comment

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")
_JSON_LITERAL = re.compile(r"^(-?\d+(\.\d+)?([eE][+-]?\d+)?|true|false|null)$")
_TOML_LITERAL = re.compile(
    r"^([+-]?\d[\d_]*(\.\d+)?([eE][+-]?\d+)?|true|false|inf|nan|0x[0-9a-fA-F_]+"
    r"|\d{4}-\d\d-\d\d.*|\[.*\]|\{.*\})$"
)
_KEY = (r"(?:[\w.\-]+|\"[^\"]*\"|'[^']*')"
        r"(?:\s*\.\s*(?:[\w\-]+|\"[^\"]*\"|'[^']*'))*")
_EQ_LINE = re.compile(rf"^(\s*)({_KEY})(\s*=\s*)(.*)$")
_COLON_LINE = re.compile(r"^(\s*)([*\w.\-]+)(\s*:\s*)(.*)$")
_YAML_LINE = re.compile(
    r"^(\s*)(\"[^\"]*\"|'[^']*'|[^\s#:'\"\-][^:#]*?)(\s*:)(\s+(?=\S)|\s*$)(.*)$"
)
_JSON_LINE = re.compile(r"^(\s*)(\"(?:[^\"\\]|\\.)*\")(\s*:\s*)(.*)$")
_WORD_LINE = re.compile(r"^(\s*)([\w_-]+)(\s+)(.*)$")
_NEEDS_SHELL_QUOTES = re.compile(r"[\s\"'`;&|<>()\\]|^$")
_YAML_SCALAR = re.compile(r"^(true|false|null|yes|no|on|off|~|-?\d+(\.\d+)?)$", re.IGNORECASE)
_NEEDS_YAML_QUOTES = re.compile(r"^[\s\-?:,\[\]{}#&*!|>'\"%@`]|:\s|\s#|\s$|^$|^(true|false|null|yes|no|on|off|~)$",
                                re.IGNORECASE)


def _read_text(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="surrogateescape",
              newline="") as f:
        return f.read()


def _atomic_write(filepath: str, text: str) -> None:
    """Replace the file in one step, keeping symlinks, mode and bytes intact."""
    target = os.path.realpath(filepath)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".dfm-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape",
                       newline="") as f:
            f.write(text)
        shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def update_config_value(filepath: str, field: ConfigField, new_value: str) -> bool:
    """Update a single value in a config file."""
    if new_value == field.value:
        return True

    try:
        content = _read_text(filepath)
    except OSError:
        return False

    lines = content.splitlines(keepends=True)
    if field.line_number < 1 or field.line_number > len(lines):
        return False

    idx = field.line_number - 1
    old_line = lines[idx]
    fmt = detect_format(filepath, content)

    if fmt == "lua":
        new_line = _rebuild_lua_line(old_line, new_value)
    else:
        new_line = _rebuild_line(old_line, field, new_value, fmt)
    if new_line is None:
        return False

    lines[idx] = new_line

    try:
        _atomic_write(filepath, "".join(lines))
        return True
    except OSError:
        return False


def _split_eol(line: str) -> tuple[str, str]:
    body = line.rstrip("\r\n")
    return body, line[len(body):]


def _split_value(rest: str, comments: bool, bare_stops_at_space: bool = False
                 ) -> tuple[str, str]:
    """Split `rest` into (value token, untouched tail such as a comment)."""
    if rest[:1] in ("'", '"'):
        quote = rest[0]
        i = 1
        while i < len(rest):
            if rest[i] == "\\" and quote == '"':
                i += 2
                continue
            if rest[i] == quote:
                return rest[:i + 1], rest[i + 1:]
            i += 1
        return rest, ""
    if bare_stops_at_space:
        m = re.match(r"^(\S*)(.*)$", rest)
        return m.group(1), m.group(2)
    if comments:
        m = re.search(r"\s+#", rest)
        if m:
            return rest[:m.start()], rest[m.start():]
    token = rest.rstrip()
    return token, rest[len(token):]


def _is_quoted(token: str) -> bool:
    return len(token) >= 2 and token[0] in "'\"" and token[-1] == token[0]


def _quote(new_value: str, quote: str) -> str:
    if quote == "'" and "'" in new_value:
        quote = '"'
    if quote == '"':
        escaped = new_value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f"'{new_value}'"


def _key_matches(field_key: str, line_key: str) -> bool:
    if len(line_key) >= 2 and line_key[0] in "'\"" and line_key[-1] == line_key[0]:
        line_key = line_key[1:-1]
    line_key = re.sub(r"\s*\.\s*", ".", line_key).replace('"', "").replace("'", "")
    return field_key == line_key or field_key.endswith("." + line_key)


def _format_value(old_token: str, new_value: str, fmt: str) -> str | None:
    """Render `new_value` the way the old token was written."""
    if _is_quoted(old_token):
        if fmt == "generic" and _is_quoted(new_value):
            return new_value
        return _quote(new_value, old_token[0])
    if fmt == "shell":
        return _quote(new_value, '"') if _NEEDS_SHELL_QUOTES.search(new_value) else new_value
    if fmt == "toml":
        return new_value if _TOML_LITERAL.match(new_value.strip()) else _quote(new_value, '"')
    if fmt == "yaml":
        if _YAML_SCALAR.match(new_value) and _YAML_SCALAR.match(old_token):
            return new_value  # a bare bool/null/number stays a bare literal
        return _quote(new_value, '"') if _NEEDS_YAML_QUOTES.search(new_value) else new_value
    return new_value


def _rebuild_line(old_line: str, field: ConfigField, new_value: str,
                  fmt: str = "generic") -> str | None:
    """Rebuild a config line with a new value, preserving formatting."""
    body, eol = _split_eol(old_line)
    rebuilt = _rebuild_body(body, field, new_value, fmt)
    return None if rebuilt is None else rebuilt + (eol or "")


def _rebuild_body(body: str, field: ConfigField, new_value: str, fmt: str) -> str | None:
    if fmt == "shell":
        return _rebuild_shell(body, field, new_value)
    if fmt == "json":
        return _rebuild_json(body, field, new_value)
    if fmt == "yaml":
        m = _YAML_LINE.match(body)
        if not m or body.lstrip().startswith("- "):
            return None
        indent, key, colon, gap, rest = m.groups()
        if not _key_matches(field.key, key):
            return None
        if not rest.strip() and field.field_type == FieldType.MULTILINE:
            return None  # block list/map on the following lines
        token, tail = _split_value(rest, comments=True)
        new = _format_value(token, new_value, fmt)
        return f"{indent}{key}{colon}{gap or ' '}{new}{tail}"
    if fmt == "i3":
        return _rebuild_i3(body, field, new_value)
    if fmt == "xresources":
        m = _COLON_LINE.match(body)
        if not m or not _key_matches(field.key, m.group(2)):
            return None
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{new_value}"

    # toml / ini / generic: `key = value`, then `key: value`, then `key value`
    m = _EQ_LINE.match(body)
    if m:
        indent, key, sep, rest = m.groups()
        if not _key_matches(field.key, key):
            return None
        token, tail = _split_value(rest, comments=(fmt == "toml"))
        if fmt == "toml" and _bracket_open(token):
            return None  # array/table spans several lines
        if fmt == "ini":
            return f"{indent}{key}{sep}{new_value}"
        new = _format_value(token, new_value, fmt)
        return f"{indent}{key}{sep}{new}{tail}"
    if fmt == "generic":
        m = _COLON_LINE.match(body)
        if m and _key_matches(field.key, m.group(2)):
            token, tail = _split_value(m.group(4), comments=False)
            new = _format_value(token, new_value, fmt)
            return f"{m.group(1)}{m.group(2)}{m.group(3)}{new}{tail}"
        m = _WORD_LINE.match(body)
        if m and _key_matches(field.key, m.group(2)):
            return f"{m.group(1)}{m.group(2)}{m.group(3)}{new_value}"
    return None


def _bracket_open(token: str) -> bool:
    stripped = re.sub(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'", "", token)
    return (stripped.count("[") + stripped.count("{")
            != stripped.count("]") + stripped.count("}"))


def _rebuild_json(body: str, field: ConfigField, new_value: str) -> str | None:
    m = _JSON_LINE.match(body)
    if not m:
        return None
    indent, key, colon, rest = m.groups()
    if not _key_matches(field.key, json.loads(key)):
        return None
    if not rest or rest[0] in "{[":
        return None
    if rest[0] == '"':
        _, tail = _split_value(rest, comments=False)
        new = json.dumps(new_value, ensure_ascii=False)
    else:
        match = re.match(r"^([^,\s]*)(.*)$", rest)
        tail = match.group(2)
        literal = new_value.strip()
        if _JSON_LITERAL.match(literal):
            new = literal
        else:
            new = json.dumps(new_value, ensure_ascii=False)
    return f"{indent}{key}{colon}{new}{tail}"


def _rebuild_shell(body: str, field: ConfigField, new_value: str) -> str | None:
    m = re.match(r"^(\s*)(export\s+)?([A-Za-z_]\w*)=(.*)$", body)
    if m and not body.lstrip().startswith(("if", "for")):
        indent, export, name, rest = m.groups()
        if name != field.key:
            return None
        token, tail = _split_value(rest, comments=False, bare_stops_at_space=True)
        new = _format_value(token, new_value, "shell")
        return f"{indent}{export or ''}{name}={new}{tail}"

    m = re.match(r"^(\s*alias\s+)([\w\-]+)=(.*)$", body)
    if m:
        if field.key != f"alias:{m.group(2)}":
            return None
        token, tail = _split_value(m.group(3), comments=False)
        new = _format_value(token, new_value, "shell")
        return f"{m.group(1)}{m.group(2)}={new}{tail}"

    m = re.match(r"^(\s*)(setopt|unsetopt)(\s+)(\w+)(.*)$", body)
    if m:
        if field.key != m.group(4) or not _bool_value(new_value):
            return None
        cmd = "setopt" if _bool_value(new_value) == "true" else "unsetopt"
        return f"{m.group(1)}{cmd}{m.group(3)}{m.group(4)}{m.group(5)}"

    m = re.match(r"^(\s*set\s+)([+-])(o\s+)(\w+)(.*)$", body)
    if m:
        if field.key != m.group(4) or not _bool_value(new_value):
            return None
        sign = "-" if _bool_value(new_value) == "true" else "+"
        return f"{m.group(1)}{sign}{m.group(3)}{m.group(4)}{m.group(5)}"

    m = re.match(r"^(\s*(?:source|\.)\s+)(.*)$", body)
    if m:
        token, tail = _split_value(m.group(2), comments=False, bare_stops_at_space=True)
        new = _format_value(token, new_value, "shell")
        return f"{m.group(1)}{new}{tail}"
    return None


def _bool_value(value: str) -> str | None:
    lowered = value.strip().lower()
    if lowered in BOOL_TRUE:
        return "true"
    if lowered in BOOL_FALSE:
        return "false"
    return None


def _rebuild_i3(body: str, field: ConfigField, new_value: str) -> str | None:
    m = re.match(r"^(\s*set\s+\$\w+\s+)(.*)$", body)
    if m:
        return f"{m.group(1)}{new_value}"
    m = re.match(r"^(\s*(?:bindsym|bindcode)\s+)(\S+)(\s+.*|)$", body)
    if m:
        if field.key != f"bind:{m.group(2)}":
            return None
        return f"{m.group(1)}{m.group(2)} {new_value}"
    m = _WORD_LINE.match(body)
    if m and field.key == m.group(2):
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{new_value}"
    return None


def _rebuild_lua_line(old_line: str, new_value: str) -> str | None:
    """Rebuild a Lua assignment, keeping quoting, commas and comments intact."""
    body = old_line.rstrip("\n")
    indent = body[:len(body) - len(body.lstrip())]

    code, comment = split_lua_comment(body.strip())
    gap = code[len(code.rstrip()):]
    code = code.rstrip()

    separator = ""
    while code.endswith((",", ";")):
        separator = code[-1] + separator
        code = code[:-1].rstrip()

    match = LUA_ASSIGNMENT.match(code)
    if match is None:
        # A keyless table item, e.g. `"waybar",` inside `exec-once = {`
        if not is_literal(code):
            return None
        return f"{indent}{_format_lua_value(code, new_value)}{separator}{gap}{comment}\n"

    prefix = code[:match.start("value")]
    value = _format_lua_value(match.group("value").strip(), new_value)

    return f"{indent}{prefix}{value}{separator}{gap}{comment}\n"


def _format_lua_value(old_value: str, new_value: str) -> str:
    """Render a new value the way the old one was written."""
    if len(old_value) >= 2 and old_value[0] == old_value[-1] and old_value[0] in "\"'":
        quote = old_value[0]
        escaped = new_value.replace("\\", "\\\\").replace(quote, f"\\{quote}")
        return f"{quote}{escaped}{quote}"

    match = LONG_STRING.match(old_value)
    if match:
        equals = match.group(1)
        return f"[{equals}[{new_value}]{equals}]"

    stripped = new_value.strip()
    lowered = stripped.lower()
    if lowered in ("nil",) or _NUMERIC.match(stripped):
        return stripped
    if lowered in BOOL_TRUE or lowered in BOOL_FALSE:
        return "true" if lowered in BOOL_TRUE else "false"

    # The old value was a bare expression (identifier, table, …) — keep it bare.
    return stripped
