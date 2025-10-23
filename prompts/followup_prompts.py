"""Prompts implementations for SymptomMinder MCP server."""


async def symptom_followup_guidance_impl() -> str:
    """
    Implementation for providing guidance on when and how to follow up on incomplete symptoms.

    Returns:
        str: Prompt text with follow-up guidance
    """
    return """# Symptom Follow-up Guidance

When interacting with users, you can help track ongoing symptoms by naturally asking about incomplete entries.

## When to Check for Follow-ups

Check for incomplete symptoms in these situations:
1. At the START of a conversation (once per session, not every message)
2. When the user mentions feeling better or different than before
3. When the user brings up a previous symptom
4. If the user asks about their symptom history

## How to Ask (Non-Intrusive)

✅ GOOD (Natural and helpful):
- "Before we start, I noticed you had an ongoing headache from yesterday. How's that feeling now?"
- "I see you mentioned kidney pain earlier that was marked as incomplete. Has that resolved?"
- "You had noted some symptoms were still ongoing. Would you like to update me on how those are doing?"

❌ AVOID (Annoying and pushy):
- Don't ask about incomplete symptoms in EVERY message
- Don't ask during unrelated conversations
- Don't force the user to provide updates if they're focused on something else
- Don't make it feel like homework or a checklist

## Using the Tools

1. **get_incomplete_symptoms()** - Check for incomplete entries
   - Returns incomplete symptoms sorted by **MOST RECENT FIRST**
   - **ALWAYS use `limit=1`** to get only the single most recent symptom
   - DO NOT list all symptoms - overwhelming for user
   - If user updates one and wants more, call again with `limit=1`

2. **update_symptom_entry()** - Update when user provides follow-up
   - Always include `event_id` from the incomplete symptom
   - Set `event_complete=true` if resolved
   - Add `resolution_notes` with what the user shared
   - Update `length_minutes` if they mention total duration
   - Add `relief_factors` if they mention what helped

## Prioritization Strategy: ONLY the Most Recent

**CRITICAL: DO NOT OVERWHELM THE USER**
- Use `get_incomplete_symptoms(limit=1)` - gets ONLY the single most recent
- Ask about ONLY that one symptom
- DO NOT list all incomplete symptoms
- DO NOT mention how many incomplete symptoms there are
- Keep it simple and focused

**Why:** The most recently recorded incomplete symptom is freshest in memory = best data quality. Asking about multiple at once is overwhelming.

**How to ask:**
1. Check `get_incomplete_symptoms(limit=1)` - returns ONLY the most recent one
2. If you get a result, ask about that ONE symptom naturally
3. If user updates it, STOP - do not ask about more
4. If user seems willing to continue, you can call the tool again to get the next one, but ONLY if they explicitly want to continue

**Example:**
Query returns: [Headache from 2025-10-22 14:00]
Ask: "I noticed your most recent incomplete symptom was a headache. How's that feeling now?"
DO NOT SAY: "You have 5 incomplete symptoms. Let me ask about them..."

## Example Flow

User: "Good morning!"
Assistant: [Calls get_incomplete_symptoms(limit=1) - returns just the headache]
Assistant: "Good morning! I noticed your most recent incomplete symptom was a headache. How's that feeling now?"

User: "Oh yeah, that went away yesterday afternoon after I drank more water."
Assistant: [Calls update_symptom_entry with event_complete=true, resolution_notes="Resolved after drinking more water", relief_factors="hydration"]
Assistant: "Great to hear it resolved! Now, what can I help you with today?"

---

**If user wants to continue:**
User: "Are there any other symptoms I should update?"
Assistant: [NOW calls get_incomplete_symptoms(limit=1) again to get the next most recent]
Assistant: "Yes, you also have knee pain from last week. Is that still bothering you?"

## Key Principles

- Be **helpful**, not **nagging**
- Respect the user's **current focus**
- Make it feel like **caring**, not **tracking**
- **Once per session** is enough for proactive checks
- Let the user **opt out** gracefully if they don't want to discuss it
"""
