from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..providers import GROK_EVENTS, default_grok_hook_config_path, detect_log_path
from ._common import (
    InstallResult,
    backup_file,
    hook_command,
    read_json_config,
    remove_json_command_hooks_for_log,
)


def install_grok_hooks(
    log_path: Path | None = None,
    config_path: Path | None = None,
    dry_run: bool = False,
    python_executable: str | None = None,
) -> InstallResult:
    config = config_path or default_grok_hook_config_path()
    target_log = (log_path or detect_log_path("grok")).expanduser()
    data = read_json_config(config)

    original = json.dumps(data, sort_keys=True)
    hooks = data.setdefault("hooks", {})
    command = hook_command("grok", target_log, python_executable)

    for event_name in GROK_EVENTS:
        entries = hooks.get(event_name, [])
        if not isinstance(entries, list):
            entries = []
        cleaned = remove_json_command_hooks_for_log(entries, target_log)
        cleaned.append(grok_hook_entry(event_name, command))
        hooks[event_name] = cleaned

    changed = json.dumps(data, sort_keys=True) != original
    backup = None
    if changed and not dry_run:
        config.parent.mkdir(parents=True, exist_ok=True)
        backup = backup_file(config)
        config.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")
        target_log.parent.mkdir(parents=True, exist_ok=True)
        target_log.touch(exist_ok=True)

    return InstallResult("grok", config, target_log, changed, backup, dry_run)


def uninstall_grok_hooks(
    log_path: Path | None = None,
    config_path: Path | None = None,
    dry_run: bool = False,
) -> InstallResult:
    config = config_path or default_grok_hook_config_path()
    target_log = (log_path or detect_log_path("grok")).expanduser()
    data = read_json_config(config)

    original = json.dumps(data, sort_keys=True)
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        for event_name in list(hooks):
            entries = hooks.get(event_name)
            if event_name not in GROK_EVENTS or not isinstance(entries, list):
                continue

            cleaned = remove_json_command_hooks_for_log(entries, target_log)
            if cleaned:
                hooks[event_name] = cleaned
            else:
                hooks.pop(event_name, None)

        if not hooks:
            data.pop("hooks", None)

    changed = json.dumps(data, sort_keys=True) != original
    backup = None
    if changed and not dry_run:
        config.parent.mkdir(parents=True, exist_ok=True)
        backup = backup_file(config)
        if data:
            config.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")
        else:
            try:
                config.unlink()
            except FileNotFoundError:
                pass

    return InstallResult("grok", config, target_log, changed, backup, dry_run)


def grok_hook_entry(event_name: str, command: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"hooks": [{"type": "command", "command": command}]}
    if event_name in {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionDenied", "Notification"}:
        entry["matcher"] = "*"
    return entry
