"""Helpers for splitting the value part of a `key = value` style line."""

import re


def is_quoted(token: str) -> bool:
    return len(token) >= 2 and token[0] in "'\"" and token[-1] == token[0]


def split_value(rest: str, comments: bool = False, bare_stops_at_space: bool = False,
                terminator: bool = False) -> tuple[str, str]:
    """Split `rest` into (value token, untouched tail).

    The tail keeps whatever follows the value: an inline comment, trailing
    whitespace, or (with `terminator`) the ';' that ends rofi/picom values.
    """
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
    if terminator and token.endswith(";"):
        token = token[:-1].rstrip()
    return token, rest[len(token):]
