import json
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser


def _matches(rule_value: Any, actual_value: str) -> bool:
    return rule_value in ("*", actual_value)


def load_permission_rules(settings: Settings) -> list[dict[str, Any]]:
    """Load simple allow-list rules. Missing config means default deny."""

    if not settings.platform_tool_permission_file:
        return []

    path = Path(settings.platform_tool_permission_file)
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data.get("allow", []) if isinstance(data, dict) else []
    return rules if isinstance(rules, list) else []


def is_tool_allowed(
    settings: Settings,
    scoped_user: ScopedUser,
    agent_id: str,
    tool_name: str,
) -> bool:
    """Default deny. A matching allow rule is required."""

    for rule in load_permission_rules(settings):
        if not isinstance(rule, dict):
            continue
        if not _matches(rule.get("tenant_id"), scoped_user.tenant_id):
            continue
        if not _matches(rule.get("user_id"), scoped_user.user_id):
            continue
        if not _matches(rule.get("agent_id"), agent_id):
            continue
        if not _matches(rule.get("tool_name"), tool_name):
            continue
        return True
    return False
