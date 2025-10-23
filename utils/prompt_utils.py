"""Prompt generation utilities for SymptomMinder."""

from symptom_schema import SymptomEntry


def generate_review_prompt(entry: SymptomEntry) -> str:
    """
    Generate human-readable review prompt for symptom entry.

    Args:
        entry: Validated SymptomEntry object

    Returns:
        Formatted review prompt string
    """
    details = entry.symptom_details
    env = entry.environmental
    summary = (
        f"Symptom: {details.symptom}\n"
        f"Severity: {details.severity}\n"
        f"Timestamp: {entry.timestamp}\n"
        f"Length (min): {details.length_minutes}\n"
        f"Location: {getattr(env, 'location', '') if env else ''}\n"
        f"Cause: {details.cause}\n"
        f"Mediation Attempt: {details.mediation_attempt}\n"
        f"On Medication: {details.on_medication}\n"
        f"Raw Notes: {details.raw_notes}\n"
        f"Event Complete: {details.event_complete}\n"
        f"Onset Type: {details.onset_type}\n"
        f"Intensity Pattern: {details.intensity_pattern}\n"
        f"Associated Symptoms: {details.associated_symptoms}\n"
        f"Relief Factors: {details.relief_factors}\n"
        f"Environmental Factors: {getattr(env, 'environmental_factors', '') if env else ''}\n"
        f"Activity Context: {getattr(env, 'activity_context', '') if env else ''}\n"
        f"Tags: {entry.tags}\n"
    )
    return (
        f"Please review the following symptom entry for accuracy before saving:\n\n"
        f"{summary}\nIs this information correct?"
    )
