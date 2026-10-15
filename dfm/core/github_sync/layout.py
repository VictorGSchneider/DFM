"""Where each dotfile lives inside a dotfiles repo.

DFM keeps your files where they are; the repo is just a copy. Two repo
layouts are understood:

- **mirror**: the repo looks like your home folder (`.bashrc`,
  `.config/hypr/hyprland.conf`). This is what DFM creates, and what most
  hand-made dotfiles repos look like.
- **stow**: one folder per program, each looking like your home folder
  (`zsh/.zshrc`, `hypr/.config/hypr/hyprland.conf`), as used with GNU Stow.

Only entries that start with a dot are ever copied back into the home folder,
so scripts, READMEs and CI files that live in an existing repo stay in the repo.
"""

import os

DEFAULT_PACKAGE = "dfm"  # where new files go in a stow-style repo

# Git's own files and the usual repo furniture; never dotfiles.
_META = {
    ".git", ".github", ".gitignore", ".gitmodules", ".gitattributes",
    ".gitkeep", ".gitlab-ci.yml", ".DS_Store",
}


def _listdir(path: str) -> list[str]:
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _packages(repo: str) -> list[str]:
    """Top-level folders of a stow-style repo."""
    return [n for n in _listdir(repo)
            if not n.startswith(".") and os.path.isdir(os.path.join(repo, n))]


def detect_layout(repo: str) -> str:
    """Return "mirror" or "stow". An empty or unclear repo counts as mirror."""
    names = [n for n in _listdir(repo) if n not in _META]
    if any(n.startswith(".") for n in names):
        return "mirror"
    for pkg in _packages(repo):
        children = _listdir(os.path.join(repo, pkg))
        if any(c.startswith(".") and c not in _META for c in children):
            return "stow"
    return "mirror"


def repo_rel(repo: str, home_rel: str, layout: str | None = None) -> str:
    """Repo-relative path for a home-relative one.

    In a stow-style repo a file already tracked under some package keeps
    living there; a new one goes into the `dfm` package.
    """
    layout = layout or detect_layout(repo)
    if layout != "stow":
        return home_rel
    for pkg in _packages(repo):
        if os.path.lexists(os.path.join(repo, pkg, home_rel)):
            return os.path.join(pkg, home_rel)
    return os.path.join(DEFAULT_PACKAGE, home_rel)


def repo_files(repo: str, layout: str | None = None) -> list[tuple[str, str]]:
    """Every dotfile in the repo as (repo-relative, home-relative) pairs."""
    layout = layout or detect_layout(repo)
    roots = [repo] if layout != "stow" else [
        os.path.join(repo, pkg) for pkg in _packages(repo)]

    found: list[tuple[str, str]] = []
    for root in roots:
        for name in _listdir(root):
            if not name.startswith(".") or name in _META:
                continue
            start = os.path.join(root, name)
            if os.path.isdir(start) and not os.path.islink(start):
                paths = []
                for dirpath, dirs, files in os.walk(start):
                    dirs[:] = [d for d in dirs if d != ".git"]
                    paths += [os.path.join(dirpath, f) for f in files]
            else:
                paths = [start]
            for path in sorted(paths):
                found.append((os.path.relpath(path, repo),
                              os.path.relpath(path, root)))
    return found
