"""
Gluten Intolerance Symptom Data Generator for SymptomMinder

Generates realistic 3-month symptom data showing gradual discovery of gluten intolerance
through a weekly pattern tied to Sunday family dinners with gluten-containing foods.
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid


class GlutenIntoleranceDataGenerator:
    """Generates realistic symptom data for gluten intolerance discovery story."""

    def __init__(
        self,
        start_date: str = "2025-08-22",
        user_id: str = "demo_user_gluten_story",
    ):
        """
        Initialize the gluten intolerance data generator.

        Args:
            start_date: ISO format start date for the data (default: 2025-08-22)
            user_id: User ID for all generated entries (default: demo_user_gluten_story)
        """
        self.start_date = datetime.fromisoformat(start_date)
        self.user_id = user_id

        # Symptom severity patterns by day of week (0=Monday, 6=Sunday)
        # Sunday evening (6): 8-10, Monday (0): 6-9, Tuesday (1): 4-7,
        # Wednesday (2): 1-4, Thu-Sat (3-5): 0-2
        self.severity_patterns = {
            6: (7, 10),  # Sunday evening - severe
            0: (6, 9),  # Monday - moderate-severe
            1: (4, 7),  # Tuesday - moderate
            2: (1, 4),  # Wednesday - mild (mostly resolved)
            3: (0, 2),  # Thursday - clear
            4: (0, 2),  # Friday - clear
            5: (0, 2),  # Saturday - clear
        }

        # Discovery timeline phases
        self.phases = {
            "confusion": 30,  # First 30 days - no pattern recognition
            "noticing": 45,  # Days 31-75 - starting to see patterns
            "discovery": 30,  # Days 76-105 - connecting to gluten/Sunday dinners
        }

        self._setup_symptom_templates()

    def _setup_symptom_templates(self):
        """Setup realistic symptom descriptions and remedies."""

        self.digestive_symptoms = {
            "bloating": {
                "descriptions": [
                    "severe abdominal bloating",
                    "stomach feels extremely distended",
                    "painful bloating and gas",
                    "abdomen feels tight and swollen",
                    "uncomfortable bloating after eating",
                ],
                "severities": (5, 10),
                "remedies": [
                    "tried gas-x",
                    "drank peppermint tea",
                    "heating pad on stomach",
                    "walked around the house",
                    "gentle stomach massage",
                    "antacids",
                ],
            },
            "stomach_pain": {
                "descriptions": [
                    "sharp stomach cramps",
                    "dull aching stomach pain",
                    "intense abdominal pain",
                    "stabbing pains in upper abdomen",
                    "burning sensation in stomach",
                ],
                "severities": (4, 9),
                "remedies": [
                    "took ibuprofen",
                    "tried tums",
                    "sipped ginger tea",
                    "laid on heating pad",
                    "took pepto bismol",
                ],
            },
            "nausea": {
                "descriptions": [
                    "persistent nausea",
                    "waves of nausea",
                    "feeling queasy and sick",
                    "mild nausea throughout day",
                    "sudden onset nausea",
                ],
                "severities": (3, 8),
                "remedies": [
                    "sipped ginger ale",
                    "tried dramamine",
                    "ate saltine crackers",
                    "stepped outside for fresh air",
                    "took deep breaths",
                ],
            },
            "diarrhea": {
                "descriptions": [
                    "urgent diarrhea",
                    "loose stools all morning",
                    "multiple trips to bathroom",
                    "watery diarrhea",
                    "digestive urgency",
                ],
                "severities": (4, 8),
                "remedies": [
                    "took imodium",
                    "stayed hydrated",
                    "ate bland foods",
                    "drank electrolyte solution",
                    "rested near bathroom",
                ],
            },
        }

        self.neurological_symptoms = {
            "headache": {
                "descriptions": [
                    "throbbing headache",
                    "dull headache behind eyes",
                    "tension headache",
                    "migraine-like pain",
                    "pressure headache",
                ],
                "severities": (3, 9),
                "remedies": [
                    "took advil",
                    "tried tylenol",
                    "laid in dark room",
                    "applied cold compress",
                    "drank more water",
                ],
            },
            "brain_fog": {
                "descriptions": [
                    "brain fog and confusion",
                    "can't think clearly",
                    "mental fatigue",
                    "difficulty concentrating",
                    "fuzzy thinking",
                ],
                "severities": (2, 7),
                "remedies": [
                    "drank coffee",
                    "took short nap",
                    "tried to focus",
                    "did light exercise",
                    "got fresh air",
                ],
            },
            "fatigue": {
                "descriptions": [
                    "extreme fatigue",
                    "exhausted despite good sleep",
                    "energy completely drained",
                    "overwhelming tiredness",
                    "feeling weak and tired",
                ],
                "severities": (4, 9),
                "remedies": [
                    "took nap",
                    "drank energy drink",
                    "went to bed early",
                    "tried B vitamins",
                    "had extra coffee",
                ],
            },
        }

        # Progressive raw notes showing discovery timeline
        self.discovery_notes = {
            "confusion": [
                "Not sure what's causing this",
                "Seems random, maybe something I ate?",
                "Feeling awful again, no idea why",
                "This keeps happening but can't figure out pattern",
                "Maybe I'm getting sick?",
                "Wondering if it's stress related",
            ],
            "noticing": [
                "This seems to happen on weekends often",
                "Monday mornings are always rough lately",
                "Starting to think it's food related",
                "Noticed this happens after big meals",
                "Weekends seem to trigger this",
                "Maybe something at family dinners?",
                "Pattern seems to be Sunday night into Monday",
            ],
            "discovery": [
                "Wondering if it's the bread at Sunday dinner",
                "Skipped bread rolls yesterday - felt much better today",
                "Think it might be gluten - Sunday dinner always has bread",
                "Connected this to gluten - family dinner has lots of bread/pasta",
                "Pretty sure it's gluten sensitivity now",
                "Avoiding gluten for a week to test theory",
                "Gluten elimination seems to be helping",
            ],
        }

        # Environmental factors
        self.locations = [
            "home",
            "work",
            "parents house",
            "restaurant",
            "family dinner",
        ]
        self.activities = [
            "after family dinner",
            "during work",
            "watching TV",
            "trying to sleep",
            "at Sunday dinner",
            "during commute",
            "relaxing at home",
        ]

    def get_phase(self, day_number: int) -> str:
        """Determine which discovery phase we're in."""
        if day_number <= 30:
            return "confusion"
        elif day_number <= 75:
            return "noticing"
        else:
            return "discovery"

    def generate_symptom_entry(self, date: datetime, day_number: int) -> Dict[str, Any]:
        """Generate a single realistic symptom entry."""
        day_of_week = date.weekday()  # 0=Monday, 6=Sunday
        phase = self.get_phase(day_number)

        # Determine if we should have symptoms this day
        severity_range = self.severity_patterns[day_of_week]
        base_severity = random.randint(*severity_range)

        # Skip entry if severity is 0-1 (clear days)
        if base_severity <= 1 and random.random() > 0.1:  # 10% chance of outlier
            return None

        # Choose symptom type based on day and severity
        if day_of_week == 6:  # Sunday evening
            # Digestive symptoms start after dinner
            symptom_types = ["bloating", "stomach_pain", "nausea"]
            entry_time = date.replace(
                hour=random.randint(18, 21), minute=random.randint(0, 59)
            )
        elif day_of_week == 0:  # Monday
            # Mix of digestive and neurological
            symptom_types = ["bloating", "diarrhea", "fatigue", "headache"]
            entry_time = date.replace(
                hour=random.randint(6, 12), minute=random.randint(0, 59)
            )
        elif day_of_week == 1:  # Tuesday
            # Lingering symptoms
            symptom_types = ["stomach_pain", "fatigue", "brain_fog"]
            entry_time = date.replace(
                hour=random.randint(8, 16), minute=random.randint(0, 59)
            )
        else:  # Wednesday - mild/outlier symptoms
            symptom_types = ["fatigue", "headache"]
            entry_time = date.replace(
                hour=random.randint(9, 17), minute=random.randint(0, 59)
            )

        # Select primary symptom
        if day_of_week == 6 and base_severity >= 8:
            # Sunday evening - often multiple symptoms
            primary_symptom = random.choice(["bloating", "stomach_pain"])
            associated = random.sample(
                [s for s in symptom_types if s != primary_symptom], random.randint(1, 2)
            )
        else:
            primary_symptom = random.choice(symptom_types)
            associated = []

        # Get symptom details
        if primary_symptom in self.digestive_symptoms:
            symptom_data = self.digestive_symptoms[primary_symptom]
        else:
            symptom_data = self.neurological_symptoms[primary_symptom]

        description = random.choice(symptom_data["descriptions"])
        severity = max(1, min(10, base_severity + random.randint(-1, 1)))
        remedy = random.choice(symptom_data["remedies"])

        # Generate raw notes based on discovery phase
        phase_notes = random.choice(self.discovery_notes[phase])
        detailed_note = f"{description}. {phase_notes}. {remedy}."

        # Determine completion status and duration
        if day_of_week >= 3:  # Thursday-Saturday usually complete quickly
            event_complete = True
            duration = random.randint(30, 180)  # 30min to 3 hours
        elif day_of_week == 2:  # Wednesday
            event_complete = random.choice([True, False])
            duration = random.randint(60, 300)  # 1-5 hours
        else:  # Sunday-Tuesday, longer lasting
            event_complete = False
            duration = random.randint(240, 720)  # 4-12 hours

        # Create the symptom entry
        entry = {
            "timestamp": entry_time.isoformat(),
            "user_id": self.user_id,
            "symptom_details": {
                "symptom": description,
                "severity": severity,
                "length_minutes": duration if event_complete else None,
                "cause": (
                    None
                    if phase == "confusion"
                    else (
                        "food related" if phase == "noticing" else "gluten sensitivity"
                    )
                ),
                "mediation_attempt": remedy,
                "on_medication": False,
                "raw_notes": detailed_note,
                "event_complete": event_complete,
                "onset_type": "gradual" if day_of_week == 6 else "sudden",
                "intensity_pattern": "constant" if severity >= 7 else "waxing/waning",
                "associated_symptoms": associated,
                "relief_factors": remedy if event_complete else None,
            },
            "environmental": {
                "location": (
                    "parents house"
                    if day_of_week == 6
                    else random.choice(self.locations)
                ),
                "activity_context": (
                    "after family dinner"
                    if day_of_week == 6
                    else random.choice(self.activities)
                ),
            },
            "tags": [
                (
                    "digestive"
                    if primary_symptom in self.digestive_symptoms
                    else "neurological"
                )
            ],
        }

        return entry

    def generate_three_months(self) -> List[Dict[str, Any]]:
        """Generate 3 months of symptom data."""
        entries = []
        current_date = self.start_date
        day_number = 1

        # Generate for approximately 90 days
        while day_number <= 90:
            entry = self.generate_symptom_entry(current_date, day_number)
            if entry:  # Only add if symptoms occurred
                entries.append(entry)

            current_date += timedelta(days=1)
            day_number += 1

        return entries

    def save_to_file(
        self,
        entries: List[Dict[str, Any]],
        filename: str = "gluten_intolerance_symptoms.json",
    ):
        """Save generated entries to JSON file."""
        with open(filename, "w") as f:
            json.dump(entries, f, indent=2)
        print(f"Generated {len(entries)} symptom entries saved to {filename}")


def main(user_id: str = None, start_date: str = None):
    """
    Generate the gluten intolerance symptom dataset.

    Args:
        user_id: Optional user ID for generated entries (default: demo_user_gluten_story)
        start_date: Optional start date in ISO format (default: 2025-08-22)
    """
    import os

    # Use environment variables or function parameters or defaults
    user_id = user_id or os.environ.get("DEMO_USER_ID", "demo_user_gluten_story")
    start_date = start_date or os.environ.get("DEMO_START_DATE", "2025-08-22")

    generator = GlutenIntoleranceDataGenerator(
        start_date=start_date, user_id=user_id
    )

    print(f"Generating 3 months of gluten intolerance symptom data...")
    print(f"User ID: {user_id}")
    print(f"Start date: {start_date}")
    print("Pattern: Severe Sunday evenings → Moderate Mon-Tue → Clear Thu-Sat")
    print(
        "Story: Gradual discovery that Sunday family dinners with bread are the cause"
    )

    entries = generator.generate_three_months()

    # Save to file
    generator.save_to_file(entries, "data/gluten_intolerance_symptoms.json")

    # Print summary
    print(f"\nGenerated {len(entries)} symptom entries")
    print(
        f"Date range: {generator.start_date.date()} to {(generator.start_date + timedelta(days=89)).date()}"
    )

    # Show sample entry
    if entries:
        print("\nSample entry:")
        print(json.dumps(entries[0], indent=2))


if __name__ == "__main__":
    main()
