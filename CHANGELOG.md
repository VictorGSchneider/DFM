# Changelog

All notable changes to DFM are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.2.0] - 2026-10-15

### Added
- **Use an existing local repo** (GitHub Sync > Setup): point DFM at a dotfiles repo you
  already cloned, with its data, on any git host. DFM shows the remote, branch, layout and
  how many dotfiles it holds before linking it; no GitHub login is needed unless the remote
  is on GitHub.
- Repos laid out like your home folder (`.bashrc`, `.config/...`) and GNU Stow-style repos
  (`zsh/.zshrc`, one folder per program) are both understood.

### Changed
- Push stages and commits only the files DFM copied, so unfinished work in the repo is
  left alone (it used to `git add -A`).
- Pull installs only dotfiles (names starting with a dot) and skips files identical to the
  ones in your home folder; scripts, READMEs and CI files in the repo no longer land in
  `~`.

## [2.1.0] - 2026-10-15

### Added
- **Missing Dependencies box** in the Analyzer: the packages your dotfiles need, the
  exact install command for your distro (apt, dnf, pacman, zypper, apk, xbps, emerge) in
  a terminal-style box, and **Copy Command** / **Open Terminal & Install** buttons.
  The terminal runs the command and DFM rescans by itself when it finishes (also when
  the window is closed early or the install fails).
- A fifth, highlighted **Missing deps** summary card in the Analyzer.
- Dotfiles you switch off stay off between runs (`~/.local/share/dfm/state.json`).
- Config pages are grouped by section (Hyprland/rofi/i3 blocks, ini sections), so repeated
  key names have context.
- The syntax-highlighting **raw viewer** is now what "View Raw" opens, a **backup history
  dialog with diffs** ("All N backups & diffs…") and the **Analyzer & Debugger** row in
  the sidebar.
- Values keep their file's syntax when edited: toggles keep `yes/no`, `on/off`, `1/0`;
  colour pickers keep Hyprland `rgba(...)` and `#rrggbbaa`; quotes, inline comments and
  the `;` terminator of rofi/picom values are preserved.
- `dfm --version` / `python -m dfm`; DFM refuses to start on GTK < 4.12 or libadwaita < 1.5
  with a clear message.
- A test suite for `dfm.core` (and smoke tests for the GTK interface), and CI that runs
  them on every pull request. Tagging `vX.Y.Z` now publishes a GitHub release.

### Changed
- GitHub actions (`gh auth status`, push, pull, clone, status) run in a background thread
  instead of freezing the window, one at a time.
- The Analyzer's **Errors** card counts configuration errors only; missing packages have
  their own card.
- Conflicts compare each file's effective (last) value and list each file once.
- Rescans keep the page you were on; loading a profile refreshes the window; deleting a
  profile asks first.
- The README documents the minimum GTK/libadwaita versions, PyYAML, and the test command.

### Fixed
- **Data loss and corruption:**
  - editing a TOML/YAML/JSON value could overwrite a different key;
  - the writer broke `alias`, `bindsym`, `set -o` and quoted lines, and dropped the `;` of
    rofi/picom values;
  - writes now go through a temporary file, so symlinks, permissions, CRLF and non-UTF-8
    bytes survive;
  - two backups in the same second overwrote each other;
  - `delete_profile("")` removed every profile, and profile names that sanitize alike
    overwrote each other;
  - importing a folder overwrote files without a backup;
  - the enabled/disabled choice was reset by every rescan.
- **Broken features:** the header Sync button and the Push/Pull menu items raised
  `AttributeError`; gist import and listing never worked (`gh gist view/list` have no
  `--json`) and the default gist target was a folder; `git pull` pulled the remote's
  default branch instead of the tracked one; a failing `git commit` was reported as
  success; commit history broke on subjects containing `|`; Export ignored the chosen
  file name; importing a non-archive said "Imported 0 files".
- **False errors and crashes:**
  - JSON containing a URL was reported as a syntax error;
  - multi-document YAML, shell `case`, heredocs and `${#a[@]}` triggered warnings;
  - one non-UTF-8 dotfile aborted the whole analysis;
  - duplicate-key and conflict checks flagged keys in different sections or blocks,
    Hyprland `bind`/`exec-once`, `if/else` branches and commented-out lines.
- SSH permission check never ran for `~/.ssh/*`; it now flags files others can write and
  private keys others can read.
- Text with `&` or `<` (aliases with `&&`, commit subjects, profile names, paths) broke
  row titles; `name { }` blocks showed up as editable `{` fields; five icons missing from
  Adwaita showed as broken images; the group titles on All Dotfiles were drawn twice.

### Removed
- The unused `dfm/ui/style.css`.

## [2.0.0] - 2026-08-19

First tracked release. A GTK4/libadwaita app that finds your dotfiles (80+ known files and
config directories), edits them in place with widgets that match each value, and:

- backs up before every edit, with restore;
- validates syntax, finds broken references, duplicates and conflicts (Analyzer);
- saves and loads profiles, installs templates and has a setup wizard;
- imports/exports archives and syncs with GitHub (repo push/pull, gist sharing) through `gh`;
- understands Lua configs (Hyprland, Neovim, WezTerm, AwesomeWM) and runs on any distro,
  not just Arch;
- ships an XDG desktop entry.

[Unreleased]: https://github.com/VictorGSchneider/DFM/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/VictorGSchneider/DFM/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/VictorGSchneider/DFM/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/VictorGSchneider/DFM/releases/tag/v2.0.0
