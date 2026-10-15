"""Edits every kind of field widget (toggle, slider, spin, text, colour) and
checks what lands in the file. Run by test_ui.py.
"""

import os, sys, tempfile, time, traceback
HOME = tempfile.mkdtemp(prefix="dfmhome")
os.environ.update(HOME=HOME, XDG_CONFIG_HOME=HOME + "/.config", XDG_DATA_HOME=HOME + "/.local/share")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FILES = {
 ".config/alacritty/alacritty.toml": '# c\n\n[font]\nsize = 11.0\n\n[window]\nopacity = 0.9\ndecor = true\n',
 ".config/picom/picom.conf": 'backend = "glx";\ninactive-opacity = 0.9;\nshadow = true;\n',
 ".config/rofi/config.rasi": 'configuration {\n    modi: "drun,run";\n    width: 40%;\n}\n',
 ".config/hypr/hyprland.conf": 'general {\n    border_size = 1\n    gaps_in = 5\n    col.active_border = rgba(33ccffee)\n}\nmisc {\n    disable_hyprland_logo = yes\n}\n',
 ".config/kitty/kitty.conf": "font_size 11.0\nbackground #101010\n",
 ".gitconfig": "[user]\n\tname = A\n\temail = a@b.c\n",
}
for rel, c in FILES.items():
    p = os.path.join(HOME, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(c)
def read(rel): return open(os.path.join(HOME, rel)).read()

import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib, Gdk
from dfm.main import DfmApplication

def pump(ms):
    end = time.time() + ms / 1000; ctx = GLib.MainContext.default()
    while time.time() < end:
        while ctx.iteration(False): pass
        time.sleep(0.01)

def widgets(root):
    out = []
    def walk(w):
        while w is not None:
            if hasattr(w, "_field"): out.append(w)
            walk(w.get_first_child()); w = w.get_next_sibling()
    walk(root.get_first_child()); return out

results = []
def check(name, rel, expected_substring=None, expected_text=None):
    got = read(rel)
    ok = (expected_text == got) if expected_text is not None else (expected_substring in got)
    results.append(ok); print("ok  " if ok else "FAIL", name, "" if ok else f"\n---- got ----\n{got}---- want ----\n{expected_text or expected_substring}")

def drive(win, toasts):
    page_of = lambda name: win.content_stack.get_child_by_name(next(e for e in win.dotfiles if e.name == name)._stack_name)
    def field(page, key):
        return next(w for w in widgets(page) if w._field.key == key)

    def edit(entry_name, key, apply, rel, **expect):
        win._on_entry_selected(next(e for e in win.dotfiles if e.name == entry_name)); pump(100)
        w = field(page_of(entry_name), key); apply(w); pump(900)
        check(f"{entry_name}:{key}", rel, **expect)

    A = ".config/alacritty/alacritty.toml"
    edit("alacritty", "window.opacity", lambda w: w.set_value(0.5), A, expected_substring="opacity = 0.5\n")
    edit("alacritty", "window.decor", lambda w: w.set_active(False), A, expected_substring="decor = false\n")
    edit("alacritty", "font.size", lambda w: w.set_value(14), A, expected_substring="size = 14\n")
    # change a slider, then change it back to its original value (must reach disk)
    edit("alacritty", "window.opacity", lambda w: w.set_value(0.9), A, expected_substring="opacity = 0.9\n")
    check("alacritty untouched lines", A, expected_text='# c\n\n[font]\nsize = 14\n\n[window]\nopacity = 0.9\ndecor = false\n')

    P = ".config/picom/picom.conf"
    edit("picom", "inactive-opacity", lambda w: w.set_value(0.7), P, expected_substring="inactive-opacity = 0.7;\n")
    edit("picom", "shadow", lambda w: w.set_active(False), P, expected_substring="shadow = false;\n")
    edit("picom", "backend", lambda w: w.set_text("xrender"), P, expected_substring='backend = "xrender";\n')

    edit("rofi", "width", lambda w: w.set_text("50%"), ".config/rofi/config.rasi", expected_substring="width: 50%;\n")
    edit("rofi", "modi", lambda w: w.set_text("drun"), ".config/rofi/config.rasi", expected_substring='modi: "drun";\n')

    H = ".config/hypr/hyprland.conf"
    win._on_entry_selected(next(e for e in win.dotfiles if e.name == "hypr")); pump(100)
    kinds = {w._field.key: type(w).__name__ for w in widgets(page_of("hypr"))}
    print("hypr widgets:", kinds)
    def recolor(w):
        c = Gdk.RGBA(); c.red, c.green, c.blue, c.alpha = 1.0, 0.0, 0.0, 238 / 255; w.set_rgba(c)
    edit("hypr", "col.active_border", recolor, H, expected_substring="col.active_border = rgba(ff0000ee)\n")
    edit("hypr", "disable_hyprland_logo", lambda w: w.set_active(False), H, expected_substring="disable_hyprland_logo = no\n")
    edit("hypr", "gaps_in", lambda w: w.set_value(8), H, expected_substring="gaps_in = 8\n")
    edit("hypr", "border_size", lambda w: w.set_value(2), H, expected_substring="border_size = 2\n")

    edit("kitty", "font_size", lambda w: w.set_value(13), ".config/kitty/kitty.conf", expected_substring="font_size 13\n")
    edit("kitty", "background", lambda w: None, ".config/kitty/kitty.conf", expected_substring="background #101010\n")
    edit(".gitconfig", "name", lambda w: w.set_text("A & B"), ".gitconfig", expected_text="[user]\n\tname = A & B\n\temail = a@b.c\n")

    print("toasts shown:", toasts)
    print("RESULT", "ALL OK" if all(results) and not toasts else "PROBLEMS")
    app.quit()

def go():
    try:
        win = app.props.active_window
        pump(500)
        toasts = []
        orig = win._toast_overlay.add_toast
        win._toast_overlay.add_toast = lambda t: (toasts.append(t.get_title()), orig(t))
        drive(win, toasts)
    except Exception:
        traceback.print_exc(); print("RESULT PROBLEMS"); app.quit()
    return False

app = DfmApplication()
GLib.timeout_add(1200, go)
app.run([])
