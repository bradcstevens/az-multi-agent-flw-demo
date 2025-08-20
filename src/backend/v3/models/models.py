from typing import Any, List

from pydantic import BaseModel


class MStep(BaseModel):
    """model of a step in a plan"""
    _agent: str = ""
    action: str = ""
    
    @property
    def agent(self):
        return self._agent

    @agent.setter
    def agent(self, value):
        self._agent = value if value is not None else ""


class MPlan(BaseModel):
    """model of a plan"""
    session_id: str = ""
    user_id: str = ""
    team_id: str = ""
    plan_id: str = ""
    user_request: str = ""
    team: List[str] = []
    facts: str = ""
    steps: List[MStep] = []

