from pydantic import BaseModel


class MemoryPlan(BaseModel):
    enabled_by_default: bool = False
    supported_modes: list[str]
    safety_notes: list[str]


def build_memory_plan() -> MemoryPlan:
    """Describe future long-term memory integration.

    Long-term memory is off by default. Later versions may enable it per Agent
    using static_control or agent_control policies.
    """

    return MemoryPlan(
        enabled_by_default=False,
        supported_modes=["static_control", "agent_control"],
        safety_notes=[
            "Do not automatically save secrets, credentials, or sensitive personal data.",
            "Memory writes must respect tenant, user, agent, and session boundaries.",
            "Enterprise deployments need retention, export, and deletion policies.",
        ],
    )
