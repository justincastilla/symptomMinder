"""Data validation and cleaning utilities for SymptomMinder."""

import copy
from typing import Any, Dict

# Null value variations to normalize
NULL_VALUES = {"none", "null", "n/a", "na", "nil", ""}


def is_null_value(value: Any) -> bool:
    """
    Check if a value represents a null value.

    Args:
        value: Value to check (typically a string)

    Returns:
        True if the value is a null-like string, False otherwise
    """
    return isinstance(value, str) and value.strip().lower() in NULL_VALUES


def clean_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and normalize entry data from client.

    Args:
        entry: Raw entry dictionary

    Returns:
        Cleaned entry dictionary with normalized values
    """
    entry = copy.deepcopy(entry)
    sd = entry.get("symptom_details")
    if sd:
        # Convert null-like strings to None or [] for lists
        for k, v in list(sd.items()):
            if is_null_value(v):
                # Use [] for known list fields, else None
                if k in ("associated_symptoms",):
                    sd[k] = []
                else:
                    sd[k] = None
        # Convert associated_symptoms to list if needed
        if "associated_symptoms" in sd and not isinstance(
            sd["associated_symptoms"], list
        ):
            if isinstance(sd["associated_symptoms"], str):
                sd["associated_symptoms"] = [sd["associated_symptoms"]]
            elif sd["associated_symptoms"] is None:
                sd["associated_symptoms"] = []
    entry["symptom_details"] = sd
    return entry


def ensure_raw_notes(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure raw_notes field is populated from description or similar fields.

    Args:
        entry: Entry dictionary with symptom_details

    Returns:
        Entry with raw_notes populated if possible
    """
    entry = copy.deepcopy(entry)
    sd = entry.get("symptom_details", {})

    # Ensure raw_notes is set to user's description if not already present
    if not sd.get("raw_notes"):
        # Prefer description, then notes, then summary, then context if present
        for field in ["description", "notes", "summary", "context"]:
            if field in sd and isinstance(sd[field], str) and sd[field].strip():
                sd["raw_notes"] = sd[field].strip()
                break

    entry["symptom_details"] = sd
    return entry
