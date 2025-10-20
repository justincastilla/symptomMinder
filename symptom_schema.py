from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SymptomDetails(BaseModel):
    """Details about a specific symptom event including severity, duration, and context."""

    symptom: str = Field(..., description="Symptom description")
    severity: int = Field(..., ge=1, le=10, description="Severity from 1 (light) to 10 (severe)")
    length_minutes: Optional[int] = Field(None, description="Duration of symptom in minutes")
    cause: Optional[str] = Field(None, description="Suspected cause of symptom")
    mediation_attempt: Optional[str] = Field(None, description="What was done to mediate symptom")
    on_medication: Optional[bool] = Field(
        None, description="Whether user was on medication at the time"
    )
    raw_notes: Optional[str] = Field(None, description="Raw notes from user")
    event_complete: Optional[bool] = Field(
        None, description="Whether the recorded event is considered complete"
    )
    onset_type: Optional[str] = Field(
        None, description="Onset type: sudden, gradual, recurring, etc."
    )
    intensity_pattern: Optional[str] = Field(
        None, description="Pattern of symptom intensity over time"
    )
    associated_symptoms: Optional[List[str]] = Field(
        None, description="Other symptoms present at the same time"
    )
    relief_factors: Optional[str] = Field(
        None, description="Factors that relieved or worsened the symptom"
    )


class EnvironmentalFactors(BaseModel):
    """Environmental and contextual factors present during a symptom event."""

    location: Optional[str] = Field(None, description="Location where symptom occurred")
    environmental_factors: Optional[Dict] = Field(
        None, description="Environmental data at the time of symptom (weather, air quality, etc.)"
    )
    activity_context: Optional[str] = Field(None, description="User activity when symptom began")


class SymptomEntry(BaseModel):
    """Complete symptom entry with timestamp, details, and environmental context."""

    timestamp: datetime = Field(..., description="Timestamp of symptom occurrence")
    user_id: Optional[str] = Field(None, description="Unique identifier for the user or patient")
    symptom_details: SymptomDetails = Field(..., description="Details of the symptom event")
    environmental: Optional[EnvironmentalFactors] = Field(
        None, description="Environmental and contextual factors"
    )
    tags: Optional[List[str]] = Field(None, description="User or system tags for this entry")
