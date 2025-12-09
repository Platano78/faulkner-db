# ~/projects/faulkner-db/core/knowledge_types.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Decision(BaseModel):
    """Represents a decision with context and alternatives"""
    id: str = Field(..., description="Unique identifier")
    description: str = Field(..., min_length=10, max_length=1000)
    rationale: str = Field(..., min_length=20, max_length=2000)
    alternatives: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    related_to: List[str] = Field(default_factory=list, description="Related decision IDs")
    source_files: List[str] = Field(default_factory=list, description="Source files where this decision was found")
    source: Optional[str] = Field(None, description="Data source: claude_code or claude_desktop")
    collection: Optional[str] = Field(None, description="ChromaDB collection: alpha or beta")
    project: Optional[str] = Field(None, description="Project name where decision was made")

    @field_validator('alternatives', 'related_to', mode='before')
    @classmethod
    def validate_non_empty_strings(cls, v):
        if isinstance(v, list):
            return [item.strip() for item in v if item and item.strip()]
        if not v or not v.strip():
            raise ValueError('Value cannot be empty')
        return v.strip()


class Pattern(BaseModel):
    """Represents a design pattern or solution template"""
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., min_length=3, max_length=100)
    implementation: str = Field(..., min_length=20, max_length=3000)
    use_cases: List[str] = Field(default_factory=list)
    context: str = Field(..., min_length=10, max_length=1000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_files: List[str] = Field(default_factory=list, description="Source files where this pattern was found")
    source: Optional[str] = Field(None, description="Data source: claude_code or claude_desktop")
    collection: Optional[str] = Field(None, description="ChromaDB collection: alpha or beta")
    project: Optional[str] = Field(None, description="Project name where pattern was found")


class Failure(BaseModel):
    """Represents a failure case with learning"""
    id: str = Field(..., description="Unique identifier")
    attempt: str = Field(..., min_length=10, max_length=1000)
    reason_failed: str = Field(..., min_length=10, max_length=2000)
    lesson_learned: str = Field(..., min_length=20, max_length=2000)
    alternative_solution: Optional[str] = Field(None, max_length=1000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_files: List[str] = Field(default_factory=list, description="Source files where this failure was documented")
    source: Optional[str] = Field(None, description="Data source: claude_code or claude_desktop")
    collection: Optional[str] = Field(None, description="ChromaDB collection: alpha or beta")
    project: Optional[str] = Field(None, description="Project name where failure occurred")


# Validators module
def validate_id(value: str) -> str:
    """Validate ID format"""
    if not value or not value.strip():
        raise ValueError("ID must be non-empty")
    return value.strip()

def validate_timestamp(dt: datetime) -> datetime:
    """Validate timestamp is not in future"""
    if dt > datetime.utcnow():
        raise ValueError("Timestamp cannot be in the future")
    return dt
