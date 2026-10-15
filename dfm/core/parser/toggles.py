"""Pick the on/off word that matches how a config file already spells it."""

# (on, off) pairs, in the order BOOL_TRUE / BOOL_FALSE know them
_PAIRS = (
    ("true", "false"),
    ("yes", "no"),
    ("on", "off"),
    ("1", "0"),
    ("enabled", "disabled"),
    ("enable", "disable"),
)


def toggle_value(old_value: str, active: bool) -> str:
    """Return the text for the new state, in the style of `old_value`.

    A file that says `yes`/`no`, `on`/`off`, `1`/`0`, ... keeps saying so (and
    keeps its capitalisation); a toggle whose old value isn't recognised falls
    back to `true`/`false`.
    """
    sample = old_value.strip()
    lowered = sample.lower()
    for on, off in _PAIRS:
        if lowered in (on, off):
            return _match_case(sample, on if active else off)
    return "true" if active else "false"


def _match_case(sample: str, word: str) -> str:
    if len(sample) > 1 and sample.isupper():
        return word.upper()
    if sample[:1].isupper():
        return word.capitalize()
    return word
