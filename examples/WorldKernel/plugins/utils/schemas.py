"""Shared pydantic schemas for WorldKernel simulation plugins.

Generic (domain-agnostic) replacements for the story_of_the_stone schemas:
the field docs no longer reference 红楼梦 characters/locations.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LongTask(BaseModel):
    """A long-horizon goal an agent pursues across many ticks."""

    task_description: str = Field(..., description="Task description, including motivation and plan")
    motivation: str = Field(..., description="The driving factor behind the task")
    plan: str = Field(..., description="The concrete content of the plan")
    created_tick: int = Field(..., description="The tick when the task was created")
    status: str = Field(default="pending", description="Task status: pending, in_progress, completed")

    def to_string(self) -> str:
        return self.task_description


class BasicAction(BaseModel):
    """A single atomic action."""

    action_type: str = Field(..., description="Action type")
    target: Optional[str] = Field(None, description="Action target")
    content: Optional[str] = Field(None, description="Action content")


class HourlyPlan(BaseModel):
    """One slot in an agent's per-day plan (12 slots per day)."""

    action: str = Field(..., description="Action description")
    time: int = Field(..., ge=0, le=12, description="Hour slot, range 0-12")
    target: str = Field(..., description="Target agent name, or 自己/无 for solo activity")
    location: str = Field(..., description="Location name where the action happens")
    importance: int = Field(..., ge=1, le=10, description="Importance score, 1-10; higher means more impactful")

    def to_list(self) -> list:
        """Serialize to [action, time, target, location, importance]."""
        return [self.action, self.time, self.target, self.location, self.importance]
