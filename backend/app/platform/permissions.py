import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser


def _matches(rule_value: Any, actual_value: str) -> bool:
    return rule_value in ("*", actual_value)


def _permission_path(settings: Settings) -> Path | None:
    if not settings.platform_tool_permission_file:
        return None
    path = Path(settings.platform_tool_permission_file)
    if not path.is_absolute():
        path = Path.cwd().joinpath(path)
    return path


def _with_rule_id(rule: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(rule)
    if not normalized.get("rule_id"):
        normalized["rule_id"] = (
            f"{normalized.get('tenant_id', 'unknown')}:"
            f"{normalized.get('user_id', 'unknown')}:"
            f"{normalized.get('agent_id', '*')}:"
            f"{normalized.get('tool_name', 'unknown')}"
        )
    return normalized


def load_permission_rules(settings: Settings) -> list[dict[str, Any]]:
    """Load simple allow-list rules. Missing config means default deny."""

    path = _permission_path(settings)
    if path is None or not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data.get("allow", []) if isinstance(data, dict) else []
    if not isinstance(rules, list):
        return []
    return [_with_rule_id(rule) for rule in rules if isinstance(rule, dict)]


def save_permission_rules(settings: Settings, rules: list[dict[str, Any]]) -> None:
    path = _permission_path(settings)
    if path is None:
        raise ValueError("PLATFORM_TOOL_PERMISSION_FILE is required.")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"allow": rules}
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_scoped_permission_rules(
    settings: Settings,
    scoped_user: ScopedUser,
) -> list[dict[str, Any]]:
    return [
        rule
        for rule in load_permission_rules(settings)
        if rule.get("tenant_id") == scoped_user.tenant_id
        and rule.get("user_id") == scoped_user.user_id
    ]


def add_scoped_permission_rule(
    settings: Settings,
    scoped_user: ScopedUser,
    agent_id: str,
    tool_name: str,
) -> dict[str, Any]:
    rules = load_permission_rules(settings)
    rule = {
        "rule_id": uuid4().hex,
        "tenant_id": scoped_user.tenant_id,
        "user_id": scoped_user.user_id,
        "agent_id": agent_id,
        "tool_name": tool_name,
    }
    rules.append(rule)
    save_permission_rules(settings, rules)
    return rule


def delete_scoped_permission_rule(
    settings: Settings,
    scoped_user: ScopedUser,
    rule_id: str,
) -> bool:
    rules = load_permission_rules(settings)
    remaining: list[dict[str, Any]] = []
    removed = False
    for rule in rules:
        if (
            rule.get("rule_id") == rule_id
            and rule.get("tenant_id") == scoped_user.tenant_id
            and rule.get("user_id") == scoped_user.user_id
        ):
            removed = True
            continue
        remaining.append(rule)
    if removed:
        save_permission_rules(settings, remaining)
    return removed


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
