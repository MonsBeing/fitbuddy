from typing import Literal

from pydantic import BaseModel, Field, field_validator

Goal = Literal["weight_loss", "muscle_gain", "general_fitness", "flexibility", "endurance"]
Intensity = Literal["low", "medium", "high"]
Experience = Literal["beginner", "intermediate", "advanced"]


class UserInput(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    user_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    age: int = Field(ge=16, le=100)
    weight: float = Field(gt=25, le=350)
    goal: Goal
    intensity: Intensity
    experience: Experience = "beginner"

    @field_validator("username", "user_id")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class FeedbackRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=40)
    feedback: str = Field(min_length=5, max_length=1000)
