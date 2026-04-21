"""Install a template onto the local filesystem."""

import os

from dfm.core.templates.types import Template


def install_template(template: Template, backup: bool = True) -> str:
    """Install a template to the filesystem. Returns status message."""
    target = os.path.expanduser(template.config_path)
    target_dir = os.path.dirname(target)

    os.makedirs(target_dir, exist_ok=True)

    if os.path.isfile(target) and backup:
        from dfm.core.backup import create_backup
        create_backup(target, reason=f"template:{template.name}")

    with open(target, "w") as f:
        f.write(template.content)

    return f"Installed {template.app_name} template to {target}"
