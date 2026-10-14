"""Find the real line of each key in TOML / YAML / JSON files.

The structured parsers work on the decoded data, which has no line
information. The writer edits files line by line, so every field needs the
line its key actually lives on. A key that cannot be located gets no line
(0) and the writer refuses to touch it rather than guessing.
"""

import json
import re

_BARE = r"[A-Za-z0-9_\-]+"
_QUOTED = r"\"[^\"]*\"|'[^']*'"
_TOML_KEY = re.compile(
    rf"^((?:{_BARE}|{_QUOTED})(?:\s*\.\s*(?:{_BARE}|{_QUOTED}))*)\s*=(.*)$"
)
_TOML_TABLE = re.compile(r"^\[(?!\[)\s*(.+?)\s*\]\s*(?:#.*)?$")
_TOML_PART = re.compile(rf"{_QUOTED}|{_BARE}")
_YAML_KEY = re.compile(r"^(\s*)(\"[^\"]*\"|'[^']*'|[^\s#:'\"\-][^:#]*?|-[^\s:][^:#]*?)\s*:(?:\s+(.*)|)$")


def _toml_parts(dotted: str) -> list[str]:
    return [p[1:-1] if p[0] in "\"'" else p for p in _TOML_PART.findall(dotted)]


def _bracket_delta(text: str) -> int:
    """Net open brackets in a TOML value, ignoring quoted strings/comments."""
    text = re.sub(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'", "", text)
    text = text.split("#", 1)[0]
    return sum(text.count(c) for c in "[{") - sum(text.count(c) for c in "]}")


def locate_toml(content: str) -> dict[str, int]:
    """Map dotted key (and table name) to its 1-based line number."""
    found: dict[str, int] = {}
    table: list[str] = []
    depth = 0
    in_multiline: str | None = None

    for num, line in enumerate(content.splitlines(), 1):
        if in_multiline:
            if in_multiline in line:
                in_multiline = None
            continue
        stripped = line.strip()
        if depth > 0:
            depth += _bracket_delta(stripped)
            continue
        if not stripped or stripped.startswith("#"):
            continue

        header = _TOML_TABLE.match(stripped)
        if header and not stripped.startswith("[["):
            table = _toml_parts(header.group(1))
            found.setdefault(".".join(table), num)
            continue
        if stripped.startswith("[["):
            table = _toml_parts(stripped.strip("[] \t").split("#", 1)[0])
            continue

        match = _TOML_KEY.match(stripped)
        if not match:
            continue
        found.setdefault(".".join(table + _toml_parts(match.group(1))), num)
        value = match.group(2)
        for quote in ('"""', "'''"):
            if value.count(quote) % 2 == 1:
                in_multiline = quote
        if not in_multiline:
            depth = max(0, _bracket_delta(value))
    return found


def locate_yaml(content: str) -> dict[str, int]:
    """Map dotted key to its 1-based line number, following indentation."""
    found: dict[str, int] = {}
    stack: list[tuple[int, str]] = []
    skip_indent: int | None = None

    for num, line in enumerate(content.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if skip_indent is not None:
            if indent > skip_indent:
                continue
            skip_indent = None
        match = _YAML_KEY.match(line)
        if not match or line.lstrip().startswith("- "):
            continue
        key = match.group(2).strip()
        if key[0] in "\"'" and key[-1] == key[0]:
            key = key[1:-1]
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        found.setdefault(".".join(k for _, k in stack), num)
        value = (match.group(3) or "").strip()
        if re.match(r"^[|>][+\-0-9]*\s*(#.*)?$", value):
            skip_indent = indent
    return found


class _JsonScanner:
    """Minimal JSON walker that records the line of every object member."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.found: dict[str, int] = {}

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            if self.text[self.pos] == "\n":
                self.line += 1
            self.pos += 1

    def _string(self) -> str:
        start = self.pos
        self.pos += 1
        while self.text[self.pos] != '"':
            self.pos += 2 if self.text[self.pos] == "\\" else 1
        self.pos += 1
        return json.loads(self.text[start:self.pos])

    def value(self, path: str) -> None:
        self._skip_ws()
        ch = self.text[self.pos]
        if ch == "{":
            self.pos += 1
            self._skip_ws()
            while self.text[self.pos] != "}":
                line = self.line
                key = self._string()
                full = f"{path}.{key}" if path else key
                self.found.setdefault(full, line)
                self._skip_ws()
                self.pos += 1  # ':'
                self.value(full)
                self._skip_ws()
                if self.text[self.pos] == ",":
                    self.pos += 1
                    self._skip_ws()
            self.pos += 1
        elif ch == "[":
            self.pos += 1
            self._skip_ws()
            index = 0
            while self.text[self.pos] != "]":
                full = f"{path}[{index}]" if path else f"[{index}]"
                self.found.setdefault(full, self.line)
                self.value(full)
                index += 1
                self._skip_ws()
                if self.text[self.pos] == ",":
                    self.pos += 1
                    self._skip_ws()
            self.pos += 1
        elif ch == '"':
            self._string()
        else:
            while self.pos < len(self.text) and self.text[self.pos] not in ",}] \t\r\n":
                self.pos += 1


def locate_json(content: str) -> dict[str, int]:
    """Map dotted key to the line its member starts on."""
    scanner = _JsonScanner(content)
    try:
        scanner.value("")
    except (IndexError, ValueError):
        pass
    return scanner.found


LOCATORS = {"toml": locate_toml, "yaml": locate_yaml, "json": locate_json}
