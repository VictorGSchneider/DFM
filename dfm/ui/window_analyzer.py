"""Analyzer & Debugger page — visual diagnostics for all dotfiles."""

import os
import shutil
import tempfile
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib, Pango

from dfm.ui.markup import esc
from dfm.core.distro import install_command
from dfm.core.scanner import DotfileEntry
from dfm.core.terminal import open_terminal
from dfm.core.analyzer import (
    analyze_all, FullAnalysis, FileAnalysis, Issue, IssueSeverity,
)


# Icons per severity
_SEV_ICON = {
    IssueSeverity.ERROR: "dialog-error-symbolic",
    IssueSeverity.WARNING: "dialog-warning-symbolic",
    IssueSeverity.INFO: "dialog-information-symbolic",
}

_SEV_CSS = {
    IssueSeverity.ERROR: "analyzer-error",
    IssueSeverity.WARNING: "analyzer-warning",
    IssueSeverity.INFO: "analyzer-info",
}

_CAT_LABELS = {
    "syntax": "Syntax",
    "file": "File System",
    "reference": "References",
    "duplicate": "Duplicates",
    "dependency": "Dependencies",
    "style": "Style",
    "pattern": "Patterns",
    "security": "Security",
    "general": "General",
}


class AnalyzerPage:
    """Builds the Analyzer & Debugger page."""

    def __init__(self, on_navigate_to_entry=None, on_install_started=None,
                 on_install_finished=None, on_message=None):
        self._on_navigate_to_entry = on_navigate_to_entry
        self._on_install_started = on_install_started    # a terminal was opened
        self._on_install_finished = on_install_finished  # (status: str) it ended
        self._on_message = on_message                    # show a short notice
        self._content_box: Gtk.Box | None = None
        self._analysis: FullAnalysis | None = None

    def build(self, dotfiles: list[DotfileEntry]) -> Gtk.Widget:
        """Build the full analyzer page."""
        self._analysis = analyze_all(dotfiles)

        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True,
        )
        clamp = Adw.Clamp(
            maximum_size=800,
            margin_start=12, margin_end=12,
            margin_top=12, margin_bottom=24,
        )
        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=16,
        )

        # Title
        title = Gtk.Label(label="Analyzer & Debugger", xalign=0)
        title.add_css_class("title-1")
        self._content_box.append(title)

        subtitle = Gtk.Label(
            label="Diagnostics for all your dotfiles in one place",
            xalign=0,
        )
        subtitle.add_css_class("dim-label")
        self._content_box.append(subtitle)

        # Summary cards
        self._content_box.append(self._build_summary(self._analysis))

        # Missing packages come first: nothing else matters without them
        if self._analysis.missing_packages:
            self._content_box.append(self._build_missing_deps(self._analysis))

        # Conflicts section
        if self._analysis.conflicts:
            self._content_box.append(self._build_conflicts(self._analysis))

        # Per-file results — problems first, then healthy
        problems = [
            fa for fa in self._analysis.file_analyses if fa.has_problems
        ]
        healthy = [
            fa for fa in self._analysis.file_analyses if not fa.has_problems
        ]

        if problems:
            header = Gtk.Label(
                label=f"Files with issues ({len(problems)})", xalign=0,
            )
            header.add_css_class("heading")
            header.set_margin_top(8)
            self._content_box.append(header)

            for fa in sorted(problems, key=lambda a: (-a.error_count, -a.warning_count)):
                self._content_box.append(self._build_file_card(fa))

        if healthy:
            # Collapsible healthy section
            expander_row = self._build_healthy_section(healthy)
            self._content_box.append(expander_row)

        clamp.set_child(self._content_box)
        scrolled.set_child(clamp)
        return scrolled

    # ── Summary ──────────────────────────────────────────────────────

    def _build_summary(self, analysis: FullAnalysis) -> Gtk.Widget:
        # Wraps onto a second line in a narrow window instead of overflowing
        box = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
            min_children_per_line=1, max_children_per_line=5,
            column_spacing=10, row_spacing=10, halign=Gtk.Align.START,
        )
        box.set_margin_top(8)

        missing = analysis.missing_dependencies
        total = len(analysis.file_analyses)
        # Ordered by how much they block: no package = the app can't run at all
        cards = [
            (str(total), "Files scanned", "analyzer-stat", None),
            (str(len(missing)), "Missing deps",
             "analyzer-error" if missing else "analyzer-ok",
             "Not installed: " + ", ".join(missing)
             if missing else "All required packages are installed"),
            (str(analysis.config_errors), "Errors", "analyzer-error", None),
            (str(analysis.total_warnings), "Warnings", "analyzer-warning", None),
            (str(analysis.healthy_count), "Healthy", "analyzer-ok", None),
        ]

        for value, label, css, tooltip in cards:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.add_css_class("analyzer-card")
            if label == "Missing deps":
                card.add_css_class("analyzer-card-alert" if missing
                                   else "analyzer-card-clear")
            if tooltip:
                card.set_tooltip_text(tooltip)

            val_label = Gtk.Label(label=value)
            val_label.add_css_class("analyzer-card-value")
            val_label.add_css_class(css)
            card.append(val_label)

            desc_label = Gtk.Label(label=label)
            desc_label.add_css_class("dim-label")
            desc_label.add_css_class("caption")
            card.append(desc_label)

            box.append(card)

        return box

    # ── Missing dependencies ─────────────────────────────────────────

    def _build_missing_deps(self, analysis: FullAnalysis) -> Gtk.Widget:
        """Everything needed to fix missing packages, in one box: what, how, go."""
        count = len(analysis.missing_packages)
        command = install_command(analysis.missing_packages)

        group = Adw.PreferencesGroup(title="Missing Dependencies")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class("card")
        box.add_css_class("missing-deps")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_icon_name(_SEV_ICON[IssueSeverity.ERROR])
        icon.add_css_class(_SEV_CSS[IssueSeverity.ERROR])
        header.append(icon)
        title = Gtk.Label(
            label=f"{count} required package{'s' if count != 1 else ''} not installed",
            xalign=0, hexpand=True,
        )
        title.add_css_class("heading")
        header.append(title)
        box.append(header)

        packages = Gtk.Label(label=", ".join(analysis.missing_dependencies),
                             xalign=0, wrap=True, selectable=True)
        packages.add_css_class("dim-label")
        box.append(packages)

        # The command, in a plain terminal-looking box (or the names, if we can't
        # build a command because the package manager isn't recognised)
        to_copy = command or " ".join(analysis.missing_packages)
        terminal_box = Gtk.Box()
        terminal_box.add_css_class("terminal-box")
        terminal_text = Gtk.Label(label=to_copy, xalign=0, wrap=True, selectable=True,
                                  wrap_mode=Pango.WrapMode.WORD_CHAR, hexpand=True)
        terminal_text.add_css_class("monospace")
        terminal_box.append(terminal_text)
        box.append(terminal_box)

        notice = Gtk.Label(
            label=("A terminal will open and run this command. "
                   "You'll type your password there, not here."
                   if command else
                   "DFM doesn't recognise this system's package manager. "
                   "Install these packages with yours."),
            xalign=0, wrap=True,
        )
        notice.add_css_class("dim-label")
        notice.add_css_class("caption")
        box.append(notice)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          halign=Gtk.Align.END)
        copy_btn = Gtk.Button(label="Copy Command" if command else "Copy Package Names")
        copy_btn.connect("clicked", lambda _b: (self._copy(to_copy),
                                                self._say("Copied to the clipboard")))
        buttons.append(copy_btn)
        if command:
            install_btn = Gtk.Button(label="Open Terminal & Install")
            install_btn.add_css_class("suggested-action")
            install_btn.connect("clicked", lambda _b: self._run_install(command))
            buttons.append(install_btn)
        box.append(buttons)

        group.add(box)
        return group

    # ── Installing missing packages ──────────────────────────────────

    def _run_install(self, command: str) -> None:
        """Open a terminal running `command`; the window rescans when it ends."""
        directory = tempfile.mkdtemp(prefix="dfm-install-")
        done_file = os.path.join(directory, "status")
        if open_terminal(command, done_file):
            self._watch_install(done_file, directory)
            if self._on_install_started:
                self._on_install_started()
            return
        shutil.rmtree(directory, ignore_errors=True)
        # No terminal emulator found: hand over the command instead
        self._copy(command)
        alert = Adw.AlertDialog()
        alert.set_heading("No terminal found")
        alert.set_body(
            "DFM couldn't find a terminal emulator to open. The command was "
            f"copied to your clipboard — paste it in any terminal:\n\n    {command}"
        )
        alert.add_response("ok", "OK")
        alert.present(self._content_box)

    def _watch_install(self, done_file: str, directory: str) -> None:
        """Tell the window when the terminal's install ends (it writes `done_file`).

        Watching a file instead of the terminal process works for emulators
        whose launcher exits immediately, and fires when the install ends, not
        when the user eventually closes the window.
        """
        started = time.monotonic()

        def poll() -> bool:
            if os.path.exists(done_file):
                try:
                    with open(done_file) as f:
                        status = f.read().strip() or "aborted"
                except OSError:
                    status = "aborted"
                shutil.rmtree(directory, ignore_errors=True)
                if self._on_install_finished:
                    self._on_install_finished(status)
                return GLib.SOURCE_REMOVE
            if time.monotonic() - started > 3 * 3600:  # nobody is coming back
                shutil.rmtree(directory, ignore_errors=True)
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add_seconds(1, poll)

    @staticmethod
    def _copy(text: str) -> None:
        display = Gdk.Display.get_default()
        if display is not None:
            display.get_clipboard().set(text)

    def _say(self, message: str) -> None:
        if self._on_message:
            self._on_message(message)

    # ── Conflicts ────────────────────────────────────────────────────

    def _build_conflicts(self, analysis: FullAnalysis) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title="Conflicts Detected")

        for conflict in analysis.conflicts:
            sev = {
                "error": IssueSeverity.ERROR,
                "warning": IssueSeverity.WARNING,
            }.get(conflict.severity, IssueSeverity.INFO)

            row = Adw.ActionRow()
            row.set_title(esc(conflict.key))
            row.set_subtitle(esc(conflict.description))

            icon = Gtk.Image.new_from_icon_name(_SEV_ICON[sev])
            icon.add_css_class(_SEV_CSS[sev])
            icon.set_valign(Gtk.Align.CENTER)
            row.add_prefix(icon)

            entries_label = Gtk.Label(
                label=" + ".join(conflict.entries),
                valign=Gtk.Align.CENTER,
            )
            entries_label.add_css_class("dim-label")
            entries_label.add_css_class("caption")
            row.add_suffix(entries_label)

            group.add(row)

        return group

    # ── File card (with issues) ──────────────────────────────────────

    def _build_file_card(self, fa: FileAnalysis) -> Gtk.Widget:
        group = Adw.PreferencesGroup()

        # Header row — file name + badge
        header_row = Adw.ActionRow()
        header_row.set_title(esc(fa.entry.display_name))
        header_row.set_subtitle(esc(fa.entry.path))

        icon = Gtk.Image.new_from_icon_name(fa.entry.icon_name)
        icon.set_pixel_size(24)
        header_row.add_prefix(icon)

        badge_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
            valign=Gtk.Align.CENTER,
        )
        if fa.error_count:
            badge_box.append(self._make_badge(
                str(fa.error_count), "analyzer-error",
            ))
        if fa.warning_count:
            badge_box.append(self._make_badge(
                str(fa.warning_count), "analyzer-warning",
            ))
        if fa.info_count:
            badge_box.append(self._make_badge(
                str(fa.info_count), "analyzer-info",
            ))
        header_row.add_suffix(badge_box)

        # Navigate button
        if self._on_navigate_to_entry:
            nav_btn = Gtk.Button(
                icon_name="go-next-symbolic",
                valign=Gtk.Align.CENTER,
                tooltip_text="Go to config",
            )
            nav_btn.add_css_class("flat")
            nav_btn._entry = fa.entry
            nav_btn.connect("clicked", self._on_nav_clicked)
            header_row.add_suffix(nav_btn)

        group.add(header_row)

        # Issue rows
        for issue in fa.issues:
            row = self._build_issue_row(issue)
            group.add(row)

        return group

    def _build_issue_row(self, issue: Issue) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(esc(issue.title))

        # Build subtitle with detail, line number, and fix hint
        parts = []
        if issue.detail:
            parts.append(issue.detail)
        if issue.fix_hint:
            parts.append(f"Fix: {issue.fix_hint}")
        row.set_subtitle(esc("\n".join(parts)))

        # Severity icon
        icon = Gtk.Image.new_from_icon_name(_SEV_ICON[issue.severity])
        icon.add_css_class(_SEV_CSS[issue.severity])
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)

        # Category chip
        cat_label = Gtk.Label(
            label=_CAT_LABELS.get(issue.category, issue.category),
            valign=Gtk.Align.CENTER,
        )
        cat_label.add_css_class("tag-chip")
        row.add_suffix(cat_label)

        # Copy fix hint if available
        if issue.fix_hint:
            copy_btn = Gtk.Button(
                icon_name="edit-copy-symbolic",
                valign=Gtk.Align.CENTER,
                tooltip_text=f"Copy: {issue.fix_hint}",
            )
            copy_btn.add_css_class("flat")
            copy_btn._text = issue.fix_hint
            copy_btn.connect("clicked", self._on_copy_hint)
            row.add_suffix(copy_btn)

        return row

    # ── Healthy files section ────────────────────────────────────────

    def _build_healthy_section(self, healthy: list[FileAnalysis]) -> Gtk.Widget:
        expander = Gtk.Expander(
            label=f"Healthy files ({len(healthy)})",
            margin_top=8,
        )
        expander.add_css_class("heading")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_top(4)

        for fa in healthy:
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                margin_top=2, margin_bottom=2,
            )

            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("analyzer-ok")
            icon.set_pixel_size(16)
            row.append(icon)

            name = Gtk.Label(label=fa.entry.display_name, xalign=0)
            name.set_hexpand(True)
            row.append(name)

            path = Gtk.Label(
                label=str(fa.entry.path), xalign=1,
                ellipsize=Pango.EllipsizeMode.MIDDLE,
            )
            path.add_css_class("dim-label")
            path.add_css_class("caption")
            row.append(path)

            if fa.info_count:
                info_badge = self._make_badge(
                    str(fa.info_count), "analyzer-info",
                )
                row.append(info_badge)

            box.append(row)

        expander.set_child(box)
        return expander

    # ── Helpers ──────────────────────────────────────────────────────

    def _make_badge(self, text: str, css_class: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.add_css_class("analyzer-badge")
        label.add_css_class(css_class)
        return label

    def _on_nav_clicked(self, btn):
        if self._on_navigate_to_entry:
            self._on_navigate_to_entry(btn._entry)

    def _on_copy_hint(self, btn):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(btn._text)
