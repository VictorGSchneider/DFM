"""Syntax validation for config files before saving."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a syntax validation check."""
    valid: bool
    errors: list[str]
    warnings: list[str]

    @property
    def summary(self) -> str:
        if self.valid and not self.warnings:
            return "Valid"
        if self.valid:
            return f"Valid ({len(self.warnings)} warnings)"
        return f"Invalid ({len(self.errors)} errors)"


def validate_file(file_path: str) -> ValidationResult:
    """Validate a config file's syntax."""
    if not os.path.isfile(file_path):
        return ValidationResult(False, ["File not found"], [])

    try:
        with open(file_path) as f:
            content = f.read()
    except OSError as e:
        return ValidationResult(False, [f"Cannot read: {e}"], [])

    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.basename(file_path).lower()

    if ext == ".json" or ext == ".jsonc":
        return _validate_json(content)
    if ext == ".toml":
        return _validate_toml(content)
    if ext in (".yaml", ".yml"):
        return _validate_yaml(content)
    if ext == ".lua":
        return _validate_lua(content)
    if ext in (".ini", ".cfg", ".conf"):
        return _validate_ini(content)
    if basename in (".bashrc", ".zshrc", ".bash_profile", ".zprofile",
                     ".profile", ".aliases"):
        return _validate_shell(content)
    if basename == ".xresources" or basename == ".xdefaults":
        return _validate_xresources(content)

    # Generic validation
    return _validate_generic(content)


def _validate_json(content: str) -> ValidationResult:
    """Validate JSON syntax."""
    errors = []
    warnings = []

    # Strip JSONC comments for validation
    cleaned = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)

    try:
        json.loads(cleaned)
    except json.JSONDecodeError as e:
        errors.append(f"JSON syntax error at line {e.lineno}, col {e.colno}: {e.msg}")

    # Warnings
    if content.strip() and not content.strip().startswith(("{", "[")):
        warnings.append("JSON should start with { or [")

    return ValidationResult(len(errors) == 0, errors, warnings)


def _validate_toml(content: str) -> ValidationResult:
    """Validate TOML syntax."""
    errors = []
    warnings = []

    try:
        import tomllib
        tomllib.loads(content)
    except ImportError:
        try:
            import tomli
            tomli.loads(content)
        except ImportError:
            # Fallback: basic structural validation
            return _validate_toml_basic(content)
        except Exception as e:
            errors.append(f"TOML error: {e}")
    except Exception as e:
        errors.append(f"TOML error: {e}")

    return ValidationResult(len(errors) == 0, errors, warnings)


def _validate_toml_basic(content: str) -> ValidationResult:
    """Basic TOML validation without library."""
    errors = []
    warnings = []

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Section headers
        if stripped.startswith("["):
            if not re.match(r'^\[[\w.\-"]+\]$', stripped) and \
               not re.match(r'^\[\[[\w.\-"]+\]\]$', stripped):
                if not stripped.endswith("]"):
                    errors.append(f"Line {i}: Unclosed section header")

        # Key-value
        elif "=" in stripped:
            key_part = stripped.split("=", 1)[0].strip()
            if not key_part:
                errors.append(f"Line {i}: Empty key")
        else:
            # Could be multiline value, skip
            pass

    return ValidationResult(len(errors) == 0, errors, warnings)


def _validate_yaml(content: str) -> ValidationResult:
    """Validate YAML syntax."""
    errors = []
    warnings = []

    try:
        import yaml
        yaml.safe_load(content)
    except ImportError:
        # Basic validation
        for i, line in enumerate(content.splitlines(), 1):
            if "\t" in line and not line.strip().startswith("#"):
                errors.append(f"Line {i}: YAML must use spaces, not tabs")
    except yaml.YAMLError as e:
        errors.append(f"YAML error: {e}")

    return ValidationResult(len(errors) == 0, errors, warnings)


_LUA_COMPILERS = ("luac", "luac5.4", "luac5.3", "luac5.2", "luac5.1", "luajit")


def _validate_lua(content: str) -> ValidationResult:
    """Validate Lua syntax, using the Lua compiler when it is installed."""
    compiler = next((c for c in _LUA_COMPILERS if shutil.which(c)), None)
    if compiler is None:
        return _validate_lua_basic(content)

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        if compiler == "luajit":
            cmd = [compiler, "-b", tmp_path, os.devnull]
        else:
            cmd = [compiler, "-p", tmp_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return _validate_lua_basic(content)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if result.returncode == 0:
        return ValidationResult(True, [], [])

    errors = []
    for line in (result.stderr or result.stdout).splitlines():
        message = line.strip()
        if not message:
            continue
        # luac: /tmp/xxx.lua:12: '}' expected near 'foo'
        message = re.sub(r"^[^\s:]*lua[^\s:]*:\s*", "", message)
        message = message.replace(tmp_path + ":", "Line ")
        errors.append(f"Lua syntax error: {message}")

    if not errors:
        errors.append("Lua syntax error (reported by the Lua compiler)")

    return ValidationResult(False, errors, [])


def _validate_lua_basic(content: str) -> ValidationResult:
    """Structural Lua checks used when no Lua compiler is available."""
    warnings = []
    code = _strip_lua_noise(content)

    for opener, closer, name in (("{", "}", "braces"), ("(", ")", "parentheses"),
                                 ("[", "]", "brackets")):
        if code.count(opener) != code.count(closer):
            warnings.append(
                f"Mismatched {name}: {code.count(opener)} '{opener}' "
                f"vs {code.count(closer)} '{closer}'"
            )

    opens = len(re.findall(r"\b(?:function|if|do)\b", code))
    ends = len(re.findall(r"\bend\b", code))
    if opens != ends:
        warnings.append(
            f"Mismatched block keywords: {opens} function/if/do vs {ends} end"
        )

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if _has_unterminated_string(stripped):
            warnings.append(f"Line {i}: Possibly unterminated string")
        code = re.sub(r"--.*$", "", stripped).rstrip()
        if re.search(r"=\s*[,;]$", code):
            warnings.append(f"Line {i}: Assignment with no value")

    return ValidationResult(True, [], warnings)


def _strip_lua_noise(content: str) -> str:
    """Remove comments and string literals so structure can be counted."""
    code = re.sub(r"--\[(=*)\[.*?\]\1\]", "", content, flags=re.DOTALL)
    code = re.sub(r"--.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"\[(=*)\[.*?\]\1\]", '""', code, flags=re.DOTALL)
    return re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", '""', code)


def _has_unterminated_string(line: str) -> bool:
    """Detect an odd number of unescaped quotes outside of comments."""
    code = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", "", line)
    code = re.sub(r"--.*$", "", code)
    return "\"" in code or "'" in code


def _validate_ini(content: str) -> ValidationResult:
    """Validate INI-style config."""
    errors = []
    warnings = []

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue

        if stripped.startswith("["):
            if not stripped.endswith("]"):
                errors.append(f"Line {i}: Unclosed section header")

    return ValidationResult(len(errors) == 0, errors, warnings)


def _validate_shell(content: str) -> ValidationResult:
    """Validate shell script syntax."""
    errors = []
    warnings = []

    # Check matching quotes
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Simple unmatched quote detection (ignoring escaped quotes)
        single_count = stripped.count("'") - stripped.count("\\'")
        double_count = stripped.count('"') - stripped.count('\\"')

        if single_count % 2 != 0 and not stripped.endswith("\\"):
            warnings.append(f"Line {i}: Possibly unmatched single quote")
        if double_count % 2 != 0 and not stripped.endswith("\\"):
            warnings.append(f"Line {i}: Possibly unmatched double quote")

    # Check matching braces/brackets
    content_no_comments = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
    opens = content_no_comments.count("{") + content_no_comments.count("(")
    closes = content_no_comments.count("}") + content_no_comments.count(")")
    if opens != closes:
        warnings.append("Mismatched braces/parentheses")

    return ValidationResult(len(errors) == 0, errors, warnings)


def _validate_xresources(content: str) -> ValidationResult:
    """Validate X Resources file."""
    errors = []
    warnings = []

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("!") or stripped.startswith("#"):
            continue

        # Lines should match pattern: resource.name: value  or  *resource: value
        if ":" not in stripped:
            warnings.append(f"Line {i}: Expected 'resource: value' format")

    return ValidationResult(len(errors) == 0, errors, warnings)


def _validate_generic(content: str) -> ValidationResult:
    """Generic validation for unknown formats."""
    warnings = []

    # Check for null bytes
    if "\x00" in content:
        return ValidationResult(False, ["File contains null bytes (binary?)"], [])

    # Check for very long lines
    for i, line in enumerate(content.splitlines(), 1):
        if len(line) > 10000:
            warnings.append(f"Line {i}: Very long line ({len(line)} chars)")

    return ValidationResult(True, [], warnings)
