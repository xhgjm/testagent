from pydantic import BaseModel


class AgentTeamPlan(BaseModel):
    enabled: bool = False
    leader_session_required: bool = True
    planned_worker_templates: list[str]


def build_agent_team_plan() -> AgentTeamPlan:
    """Describe future Agent Team integration.

    TODO: Register AgentScope SubAgentTemplate worker types such as explorer,
    coder, tester, and reviewer after the Agent Service main chain is stable.
    """

    return AgentTeamPlan(
        enabled=False,
        leader_session_required=True,
        planned_worker_templates=["explorer", "coder", "tester", "reviewer"],
    )
