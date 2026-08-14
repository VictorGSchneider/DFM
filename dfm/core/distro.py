"""Distro detection - package-manager abstraction.

Everything else in DFM is distro-agnostic: the scanner walks XDG paths, the
parsers are pure Python, and nothing hardcodes a system path. The one place
that has to know what system it is running on is dependency advice — telling
the user whether a package is installed and how to install it.

This module isolates that knowledge. Package names in the rest of the
codebase are *canonical ids* (Arch names, historically); `package_name()`
translates one to whatever the local package manager calls it.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field


# How a query proves a package is installed.
BY_RETURNCODE = "returncode"   # exit 0 means installed
BY_STDOUT = "stdout"           # non-empty stdout means installed
BY_DPKG_STATUS = "dpkg"        # parse dpkg-query's Status field


@dataclass(frozen=True)
class PackageManager:
    """A system package manager and how to drive it."""
    id: str
    display_name: str
    binary: str                    # proves this manager is the local one
    install: tuple[str, ...]       # argv prefix for installing packages
    query: tuple[str, ...]         # argv prefix for "is <pkg> installed?"
    query_mode: str = BY_RETURNCODE
    update: str = ""               # full-system upgrade, for shell aliases
    autoremove: str = ""           # prune orphans, for shell aliases


# Ordered by specificity. Detection walks this list and takes the first
# manager whose binaries are actually present, so a Debian box with rpm
# installed for other reasons still resolves to apt.
MANAGERS: tuple[PackageManager, ...] = (
    PackageManager(
        id="pacman", display_name="pacman", binary="pacman",
        install=("sudo", "pacman", "-S"),
        query=("pacman", "-Qi"),
        update="sudo pacman -Syu",
        autoremove="sudo pacman -Rns $(pacman -Qdtq)",
    ),
    PackageManager(
        id="apt", display_name="APT", binary="apt",
        install=("sudo", "apt", "install"),
        query=("dpkg-query", "-W", "-f=${Status}"),
        query_mode=BY_DPKG_STATUS,
        update="sudo apt update && sudo apt upgrade",
        autoremove="sudo apt autoremove",
    ),
    PackageManager(
        id="dnf", display_name="DNF", binary="dnf",
        install=("sudo", "dnf", "install"),
        query=("rpm", "-q"),
        update="sudo dnf upgrade",
        autoremove="sudo dnf autoremove",
    ),
    PackageManager(
        id="zypper", display_name="zypper", binary="zypper",
        install=("sudo", "zypper", "install"),
        query=("rpm", "-q"),
        update="sudo zypper update",
        autoremove="sudo zypper packages --orphaned",
    ),
    PackageManager(
        id="apk", display_name="apk", binary="apk",
        install=("sudo", "apk", "add"),
        query=("apk", "info", "-e"),
        query_mode=BY_STDOUT,
        update="sudo apk upgrade",
        autoremove="sudo apk del --purge",
    ),
    PackageManager(
        id="xbps", display_name="XBPS", binary="xbps-install",
        install=("sudo", "xbps-install", "-S"),
        query=("xbps-query",),
        update="sudo xbps-install -Su",
        autoremove="sudo xbps-remove -O",
    ),
    PackageManager(
        id="emerge", display_name="Portage", binary="emerge",
        install=("sudo", "emerge", "--ask"),
        query=("qlist", "-I"),
        query_mode=BY_STDOUT,
        update="sudo emerge --sync && sudo emerge -uDN @world",
        autoremove="sudo emerge --depclean",
    ),
)

_MANAGERS_BY_ID = {m.id: m for m in MANAGERS}

# os-release ID / ID_LIKE -> manager id. Only used to order the search, so a
# distro that ships more than one manager resolves to its native one.
_OS_RELEASE_HINTS = {
    "arch": "pacman", "archlinux": "pacman", "manjaro": "pacman",
    "endeavouros": "pacman", "cachyos": "pacman", "garuda": "pacman",
    "debian": "apt", "ubuntu": "apt", "linuxmint": "apt", "pop": "apt",
    "raspbian": "apt",
    "fedora": "dnf", "rhel": "dnf", "centos": "dnf", "rocky": "dnf",
    "almalinux": "dnf",
    "opensuse": "zypper", "suse": "zypper", "opensuse-tumbleweed": "zypper",
    "opensuse-leap": "zypper", "sles": "zypper",
    "alpine": "apk",
    "void": "xbps",
    "gentoo": "emerge",
}


def _read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, "r", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    data[key.strip()] = value.strip().strip('"').strip("'")
            break
        except OSError:
            continue
    return data


def _preferred_ids() -> list[str]:
    """Manager ids suggested by os-release, most specific first."""
    info = _read_os_release()
    ids: list[str] = []
    if info.get("ID"):
        ids.append(info["ID"].lower())
    ids.extend(part.lower() for part in info.get("ID_LIKE", "").split())
    out: list[str] = []
    for name in ids:
        mid = _OS_RELEASE_HINTS.get(name)
        if mid and mid not in out:
            out.append(mid)
    return out


def _usable(manager: PackageManager) -> bool:
    """Both the install binary and the query binary must exist."""
    return (shutil.which(manager.binary) is not None
            and shutil.which(manager.query[0]) is not None)


_detected: PackageManager | None = None
_detected_done = False


def detect_manager() -> PackageManager | None:
    """The local package manager, or None if we don't recognise this system."""
    global _detected, _detected_done
    if _detected_done:
        return _detected

    ordered: list[PackageManager] = []
    for mid in _preferred_ids():
        manager = _MANAGERS_BY_ID.get(mid)
        if manager is not None:
            ordered.append(manager)
    ordered.extend(m for m in MANAGERS if m not in ordered)

    _detected = next((m for m in ordered if _usable(m)), None)
    _detected_done = True
    return _detected


def distro_name() -> str:
    """Human-readable distro name, for display only."""
    info = _read_os_release()
    return info.get("PRETTY_NAME") or info.get("NAME") or "this system"


# ── Package naming ───────────────────────────────────────────────────

# canonical id -> {manager id: local name}. Only list the ones that differ
# from the canonical id; anything absent falls through unchanged.
_NAMES: dict[str, dict[str, str]] = {
    "i3-wm": {"apt": "i3-wm", "dnf": "i3", "zypper": "i3", "apk": "i3wm",
              "xbps": "i3", "emerge": "x11-wm/i3"},
    "dmenu": {"apt": "suckless-tools", "emerge": "x11-misc/dmenu"},
    "gtk3": {"apt": "libgtk-3-0", "dnf": "gtk3", "zypper": "gtk3",
             "apk": "gtk+3.0", "xbps": "gtk+3", "emerge": "x11-libs/gtk+"},
    "gtk4": {"apt": "libgtk-4-1", "dnf": "gtk4", "zypper": "gtk4",
             "apk": "gtk4.0", "xbps": "gtk4", "emerge": "gui-libs/gtk"},
    "nodejs": {"emerge": "net-libs/nodejs"},
    "npm": {"dnf": "nodejs-npm", "emerge": "net-libs/nodejs"},
    "python-pynvim": {"apt": "python3-pynvim", "dnf": "python3-neovim",
                      "zypper": "python3-pynvim", "apk": "py3-pynvim",
                      "xbps": "python3-pynvim", "emerge": "dev-python/pynvim"},
    "fd": {"apt": "fd-find", "dnf": "fd-find", "zypper": "fd",
           "emerge": "sys-apps/fd"},
    "ripgrep": {"emerge": "sys-apps/ripgrep"},
    "lua": {"apt": "lua5.4", "apk": "lua5.4", "emerge": "dev-lang/lua"},
    "github-cli": {"apt": "gh", "dnf": "gh", "zypper": "gh", "xbps": "github-cli",
                   "emerge": "dev-vcs/github-cli"},
    "otf-font-awesome": {"apt": "fonts-font-awesome", "dnf": "fontawesome-fonts",
                         "zypper": "fontawesome-fonts", "apk": "font-awesome",
                         "xbps": "font-awesome", "emerge": "media-fonts/fontawesome"},
    "ttf-font-awesome": {"apt": "fonts-font-awesome", "dnf": "fontawesome-fonts",
                         "zypper": "fontawesome-fonts", "apk": "font-awesome",
                         "xbps": "font-awesome", "emerge": "media-fonts/fontawesome"},
    "ttf-nerd-fonts-symbols": {"apt": "fonts-hack", "dnf": "nerd-fonts",
                               "apk": "font-nerd-fonts-symbols",
                               "xbps": "nerd-fonts-symbols-ttf"},
    "pulseaudio": {"emerge": "media-sound/pulseaudio"},
    "zsh-completions": {"apt": "zsh-common", "emerge": "app-shells/zsh-completions"},
    "awesome": {"emerge": "x11-wm/awesome"},
    "neovim": {"emerge": "app-editors/neovim"},
    "vim": {"emerge": "app-editors/vim"},
    "git": {"emerge": "dev-vcs/git"},
    "tmux": {"emerge": "app-misc/tmux"},
    "mpv": {"emerge": "media-video/mpv"},
    "fish": {"emerge": "app-shells/fish"},
    "zsh": {"emerge": "app-shells/zsh"},
}


def package_name(canonical: str) -> str:
    """Translate a canonical package id to the local package manager's name."""
    manager = detect_manager()
    if manager is None:
        return canonical
    return _NAMES.get(canonical, {}).get(manager.id, canonical)


# ── Installed-state detection ────────────────────────────────────────

@dataclass(frozen=True)
class Proof:
    """Evidence that a package is present, independent of how it was installed.

    Package databases only know about packages *they* installed, and package
    names differ wildly across distros. These checks catch the rest: a
    self-compiled compositor, a pip-installed binding, a differently named
    Debian binary.
    """
    binaries: tuple[str, ...] = ()
    pkgconfig: tuple[str, ...] = ()
    python_modules: tuple[str, ...] = ()
    fonts: tuple[str, ...] = ()


# Only needed where the canonical id is not itself the binary name. Anything
# absent defaults to Proof(binaries=(canonical,)), which covers the majority
# (alacritty, kitty, rofi, dunst, waybar, tmux, git, …).
_PROOFS: dict[str, Proof] = {
    "i3-wm": Proof(binaries=("i3",)),
    "hyprland": Proof(binaries=("Hyprland", "hyprland")),
    "neovim": Proof(binaries=("nvim",)),
    "nodejs": Proof(binaries=("node", "nodejs")),
    "ripgrep": Proof(binaries=("rg",)),
    # Debian ships fd as fdfind to avoid a name clash.
    "fd": Proof(binaries=("fd", "fdfind")),
    "lua": Proof(binaries=("lua", "lua5.4", "lua5.3", "luajit",
                           "luac", "luac5.4", "luac5.3")),
    "python-pynvim": Proof(python_modules=("pynvim",)),
    "github-cli": Proof(binaries=("gh",)),
    "pulseaudio": Proof(binaries=("pulseaudio", "pipewire-pulse")),
    "gtk3": Proof(pkgconfig=("gtk+-3.0",)),
    "gtk4": Proof(pkgconfig=("gtk4",)),
    "otf-font-awesome": Proof(fonts=("Font Awesome",)),
    "ttf-font-awesome": Proof(fonts=("Font Awesome",)),
    "ttf-nerd-fonts-symbols": Proof(fonts=("Nerd Font", "Symbols Nerd Font")),
    # Plugin packages are plain files with no binary; leave them to the
    # package database.
    "zsh-completions": Proof(),
    "zsh-syntax-highlighting": Proof(),
    "zsh-autosuggestions": Proof(),
}


def _run(argv: list[str], timeout: int = 5) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout)
    except (subprocess.SubprocessError, OSError):
        return None


_font_list: str | None = None


def _has_font(needle: str) -> bool:
    global _font_list
    if _font_list is None:
        if shutil.which("fc-list") is None:
            _font_list = ""
        else:
            result = _run(["fc-list"], timeout=10)
            _font_list = (result.stdout if result else "") or ""
    return needle.lower() in _font_list.lower()


def _has_pkgconfig(module: str) -> bool:
    if shutil.which("pkg-config") is None:
        return False
    result = _run(["pkg-config", "--exists", module])
    return result is not None and result.returncode == 0


def _has_python_module(name: str) -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _proof_satisfied(canonical: str) -> bool:
    proof = _PROOFS.get(canonical)
    if proof is None:
        return shutil.which(canonical) is not None
    if any(shutil.which(b) for b in proof.binaries):
        return True
    if any(_has_pkgconfig(m) for m in proof.pkgconfig):
        return True
    if any(_has_python_module(m) for m in proof.python_modules):
        return True
    if any(_has_font(f) for f in proof.fonts):
        return True
    return False


def _pkgdb_says_installed(canonical: str) -> bool:
    manager = detect_manager()
    if manager is None:
        return False
    result = _run([*manager.query, package_name(canonical)])
    if result is None:
        return False
    if manager.query_mode == BY_STDOUT:
        return bool(result.stdout.strip())
    if manager.query_mode == BY_DPKG_STATUS:
        return "install ok installed" in result.stdout
    return result.returncode == 0


_installed_cache: dict[str, bool] = {}


def is_installed(canonical: str) -> bool:
    """Whether a canonical package is present on this system.

    Checks direct evidence first (a binary on PATH, a pkg-config module, an
    importable Python module, a registered font), because that is true
    regardless of which distro packaged it or whether it was packaged at all.
    Falls back to querying the native package database, which catches
    packages that ship no binary of their own.
    """
    if canonical in _installed_cache:
        return _installed_cache[canonical]
    result = _proof_satisfied(canonical) or _pkgdb_says_installed(canonical)
    _installed_cache[canonical] = result
    return result


# ── Install commands ─────────────────────────────────────────────────

def install_command(canonicals: list[str]) -> str | None:
    """Shell command that installs the given canonical packages, if known."""
    if not canonicals:
        return None
    manager = detect_manager()
    if manager is None:
        return None
    names = [package_name(c) for c in canonicals]
    return " ".join([*manager.install, *names])


def install_hint(canonical: str) -> str:
    """One-package install advice, safe to show even on an unknown distro."""
    command = install_command([canonical])
    if command:
        return command
    return f"Install the '{canonical}' package for {distro_name()}"


def update_alias() -> str:
    """Full-system upgrade command, for generated shell aliases."""
    manager = detect_manager()
    return manager.update if manager else "echo 'no known package manager'"


def autoremove_alias(shell: str = "posix") -> str:
    """Orphan-cleanup command, for generated shell aliases.

    Fish spells command substitution `(cmd)` rather than `$(cmd)`, so the
    pacman form has to be adjusted when it lands in a fish config.
    """
    manager = detect_manager()
    if manager is None:
        return "echo 'no known package manager'"
    command = manager.autoremove
    if shell == "fish":
        command = command.replace("$(", "(")
    return command
