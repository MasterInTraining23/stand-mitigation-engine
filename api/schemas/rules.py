from typing import Optional, List
from pydantic import BaseModel


class MitigationCreate(BaseModel):
    type: str
    name: str
    description: Optional[str] = None
    modifier_params: Optional[dict] = None


class RuleCreate(BaseModel):
    slug: str
    category: str
    name: str
    written_rule: str
    type: str
    definition: dict
    author_id: str
    author_name: str
    change_note: Optional[str] = None
    mitigations: List[MitigationCreate] = []


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    written_rule: Optional[str] = None
    definition: Optional[dict] = None
    author_id: str
    author_name: str
    change_note: Optional[str] = None
    mitigations: Optional[List[MitigationCreate]] = None


class TransitionRequest(BaseModel):
    to_status: str
    author_id: str
    author_name: str
    note: Optional[str] = None


class TestRuleRequest(BaseModel):
    observations: dict
