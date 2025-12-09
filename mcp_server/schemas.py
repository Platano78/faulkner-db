from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class DecisionInput(BaseModel):
    description: str = Field(..., min_length=10, max_length=1000)
    rationale: str = Field(..., min_length=20, max_length=2000)
    alternatives: List[str] = Field(default_factory=list)
    related_to: List[str] = Field(default_factory=list)


class PatternInput(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    implementation: str = Field(..., min_length=20, max_length=3000)
    use_cases: List[str] = Field(default_factory=list)
    context: str = Field(..., min_length=10, max_length=1000)


class FailureInput(BaseModel):
    attempt: str = Field(..., min_length=10, max_length=1000)
    reason_failed: str = Field(..., min_length=10, max_length=2000)
    lesson_learned: str = Field(..., min_length=20, max_length=2000)
    alternative_solution: Optional[str] = Field(None, max_length=1000)


class TimelineEntry(BaseModel):
    timestamp: datetime
    type: str
    content: Dict[str, Any]
    id: str


class GapReportOutput(BaseModel):
    gap_type: str
    affected_nodes: List[str]
    severity: str
    recommendation: str
    metrics: Dict[str, Any]
