from typing import Literal
from pydantic import BaseModel, Field

class AnomalyRiskAssessment(BaseModel):
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="The assessed severity level of the detected anomaly."
    )
    rationale: str = Field(
        description="Detailed explanation justifying the assigned severity and identifying the pattern characteristics."
    )
    recommended_action: str = Field(
        description="Specific compliance or risk action that should be taken based on the anomaly assessment."
    )
