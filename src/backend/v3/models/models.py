from typing import List, Any
from pydantic import BaseModel

class m_step(BaseModel):
    """model of a step in a plan"""
    _agent: str = ""
    action: str = ""
    
    @property
    def agent(self):
        return self._agent

    @agent.setter
    def agent(self, value):
        self._agent = value if value is not None else ""


class m_plan(BaseModel):
    """model of a plan"""
    team_id: str = ""
    plan_id: str = ""
    user_request: str = ""
    team: List[str] = []
    facts: str = ""
    steps: List[m_step] = []

