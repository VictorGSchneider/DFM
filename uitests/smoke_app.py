"""Builds every page and dialog of the real app with awkward content (markup
characters, non-UTF-8 bytes, conflicts, missing packages). Run by test_ui.py.
"""

import os, sys, subprocess, tempfile, traceback, time
HOME = tempfile.mkdtemp(prefix="dfmhome")
os.environ["HOME"] = HOME
os.environ["XDG_CONFIG_HOME"] = HOME + "/.config"
os.environ["XDG_DATA_HOME"] = HOME + "/.local/share"
os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def w(rel, content):
    p = os.path.join(HOME, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content); return p

w(".bashrc", "# main\nexport EDITOR=vim\nexport TAG=\"<b>x</b> & more\"\nalias up='sudo apt update && sudo apt upgrade'\nalias ll='ls -la'\nsource ~/x.sh # old\nsource <(fzf --zsh)\nsetopt autocd\n")
w(".zshrc", "export EDITOR=nano\nalias ll='ls -lah > /dev/null'\nalias up='a && b'\n")
w(".gitconfig", "[user]\n\tname = A & B\n\temail = a@b.c\n[alias]\n\tname = x\n")
w(".config/i3/config", "set $mod Mod4\nbindsym $mod+Return exec alacritty\nfont pango:monospace 8\nexec --no-startup-id dunst &\n")
w(".config/nvim/init.lua", 'vim.opt.number = true\nvim.o.tabstop = 4\nlocal x = "a & <b>"\n')
w(".config/alacritty/alacritty.toml", '# c\n\n[font]\nsize = 11.0\n\n[window]\nopacity = 0.9\ndecor = true\n')
w(".config/waybar/config", '{\n  "layer": "top",\n  "url": "https://example.com/a&b",\n  "modules-left": ["a", "b"]\n}\n')
w(".config/rofi/config.rasi", 'configuration {\n    modi: "drun,run";\n    width: 40%;\n}\n')
w(".config/picom/picom.conf", 'backend = "glx";\ninactive-opacity = 0.9;\nshadow = true;\n')
w(".config/kitty/kitty.conf", "font_size 11.0\nbackground #101010\n")
open(HOME + "/.bashrc", "ab").write(b"# caf\xe9\n")        # non-UTF-8 byte

import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib

from dfm.core import profiles, backup
from dfm.core.github_sync import save_repo_path
from dfm.core.scanner import scan_dotfiles

# profile + backup with hostile names
ents = scan_dotfiles()
profiles.save_profile("R&D <test>", "desc & <more>", ents)
backup.create_backup(HOME + "/.bashrc", "profile-load:R&D <test>")
# a git repo with a hostile commit subject
repo = HOME + "/.dotfiles"; os.makedirs(repo)
g = lambda *a: subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@e", *a], cwd=repo, capture_output=True, check=True)
g("init", "-q"); open(repo + "/f", "w").write("1"); g("add", "-A"); g("commit", "-q", "-m", "fix: a & <b> | c")
save_repo_path(repo)

from dfm.main import DfmApplication

errors = []
def pump(ms=400):
    end = time.time() + ms / 1000
    ctx = GLib.MainContext.default()
    while time.time() < end:
        while ctx.iteration(False):
            pass
        time.sleep(0.01)

errors = []
def step(name, fn):
    try:
        fn(); pump()
        print("ok  ", name)
    except Exception:
        print("FAIL", name); traceback.print_exc(); errors.append(name)

def drive(app):
    win = app.props.active_window
    pump(1000)
    step("all-dotfiles", lambda: win._on_entry_selected(None))
    for e in list(win.dotfiles):
        step(f"entry {e.name}", lambda e=e: win._on_entry_selected(e))
    step("analyzer", win._on_analyzer_selected)
    step("profiles dialog", win._on_profiles)
    step("templates dialog", win._on_templates)
    step("wizard dialog", win._on_wizard)
    step("about", lambda: win._on_about())
    step("rescan", win._scan_and_populate)
    print("SMOKE", "FAILED" if errors else "OK", errors)
    app.quit()

def go():
    try:
        drive(app)
    except Exception:
        traceback.print_exc(); print("SMOKE FAILED"); app.quit()
    return False

app = DfmApplication()
GLib.timeout_add(1200, go)
app.run([])
