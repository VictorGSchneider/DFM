"""Check the GUI toolkit is new enough before the app starts."""

MIN_GTK = (4, 12)   # Gtk.CssProvider.load_from_string, FileDialog, ColorDialog
MIN_ADW = (1, 5)    # Adw.AlertDialog, Adw.AboutDialog, Adw.Dialog


def runtime_problem(gtk: tuple[int, int], adw: tuple[int, int]) -> str | None:
    """A message explaining what is too old, or None if this runtime will do."""
    problems = []
    if gtk < MIN_GTK:
        problems.append(f"GTK {MIN_GTK[0]}.{MIN_GTK[1]} or newer "
                        f"(found {gtk[0]}.{gtk[1]})")
    if adw < MIN_ADW:
        problems.append(f"libadwaita {MIN_ADW[0]}.{MIN_ADW[1]} or newer "
                        f"(found {adw[0]}.{adw[1]})")
    if not problems:
        return None
    return "DFM needs " + " and ".join(problems) + "."
