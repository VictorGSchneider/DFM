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
             "Not installed: " + ", ".join(missing) + "\n\nClick to install them"
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
            shown: Gtk.Widget = card
            if label == "Missing deps" and missing:
                # A button, so it's reachable by keyboard and shows a hover state
                shown = Gtk.Button(child=card, tooltip_text=tooltip)
                shown.add_css_class("flat")
                shown.add_css_class("analyzer-card-button")
                shown.connect("clicked", self._on_install_clicked, analysis)
            elif tooltip:
                card.set_tooltip_text(tooltip)

            val_label = Gtk.Label(label=value)
            val_label.add_css_class("analyzer-card-value")
            val_label.add_css_class(css)
            card.append(val_label)

            desc_label = Gtk.Label(label=label)
            desc_label.add_css_class("dim-label")
            desc_label.add_css_class("caption")
            card.append(desc_label)

            box.append(shown)

        return box

    # ── Installing missing packages ──────────────────────────────────

    def _on_install_clicked(self, button: Gtk.Button, analysis: FullAnalysis) -> None:
        names = analysis.missing_dependencies
        command = install_command(analysis.missing_packages)
        listing = "\n".join(f"  •  {n}" for n in names)

        dialog = Adw.AlertDialog()
        dialog.add_response("cancel", "Cancel")
        dialog.set_close_response("cancel")
        if command:
            dialog.set_heading("Install missing packages?")
            dialog.set_body(
                "Your dotfiles need these packages, which aren't installed:\n\n"
                f"{listing}\n\n"
                f"A terminal will open and run:\n    {command}\n\n"
                "You'll type your password in that terminal, not here."
            )
            dialog.add_response("copy", "Copy Command")
            dialog.add_response("install", "Open Terminal & Install")
            dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("install")
        else:
            dialog.set_heading("Install missing packages")
            dialog.set_body(
                "DFM doesn't recognise this system's package manager, so it can't "
                "build an install command. Install these with your package "
                f"manager:\n\n{listing}"
            )
            command = " ".join(analysis.missing_packages)
            dialog.add_response("copy", "Copy Package Names")
        dialog.connect("response", self._on_install_response, command)
        dialog.present(button)

    def _on_install_response(self, dialog, response: str, command: str) -> None:
        if response == "copy":
            self._copy(command)
            self._say("Copied to the clipboard")
        elif response == "install":
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
