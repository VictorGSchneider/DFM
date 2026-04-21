"""Dialog classes for profiles, templates, wizard, and diff viewer."""

from dfm.ui.window_dialogs.profiles import ProfilesDialog
from dfm.ui.window_dialogs.templates import TemplatesDialog
from dfm.ui.window_dialogs.wizard import WizardDialog
from dfm.ui.window_dialogs.diff_viewer import DiffViewerDialog
from dfm.ui.window_dialogs.backup_history import BackupHistoryDialog

__all__ = [
    "ProfilesDialog",
    "TemplatesDialog",
    "WizardDialog",
    "DiffViewerDialog",
    "BackupHistoryDialog",
]
