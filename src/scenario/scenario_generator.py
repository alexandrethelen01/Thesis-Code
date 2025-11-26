import json
from typing import Dict, Any

from src.models.llm_client import LLMClient
from src.config import DEFAULT_URL


SCENARIO_SYSTEM_PROMPT = """
You convert a user's natural-language description of a UI test
into a structured test scenario for an automated testing agent.

Return ONLY a valid JSON object with this structure:

{
  "url": "<string, optional: URL to open, or empty for default>",
  "goal": "<short sentence summarising the test goal>",
  "subtasks": [
    "<step 1: a SINGLE concrete UI action or sub-goal>",
    "<step 2>",
    "..."
  ],
  "assertions": [
    "<visual condition 1>",
    "<visual condition 2>",
    "..."
  ]
}

Rules for 'subtasks':
- Subtasks MUST be ordered.
- Each subtask must be SMALL and ACTIONABLE, something that could be done in a handful of clicks/keystrokes.
- Use clear language like:
  - "Type standard_user into the username field"
  - "Type secret_sauce into the password field"
  - "Click the Login button"
  - "Wait for the products page to load"
  - "Click the first visible Add to cart button"
  - "Open the shopping cart page"
- Do NOT compress multiple actions into one subtask. For example,
  "Log in with valid credentials" is TOO VAGUE; instead, split into separate subtasks:
  "Type username ...", "Type password ...", "Click Login".

Rules for 'assertions':
- Assertions MUST be conditions that can be checked visually on a screenshot.
- Examples:
  - "The cart contains exactly one item"
  - "No UI elements overlap in the header"
  - "The error message 'Invalid credentials' is visible"

If the user does not specify a URL, set "url" to "" (empty string).
Do NOT include any comments or extra text outside the JSON.
"""



class ScenarioGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def parse_prompt(self, user_prompt: str) -> Dict[str, Any]:
        full_prompt = (
            SCENARIO_SYSTEM_PROMPT
            + "\n\nUSER TEST DESCRIPTION:\n"
            + user_prompt.strip()
        )

        raw = self.llm.generate(full_prompt)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw}")

        url = data.get("url") or DEFAULT_URL
        goal = data.get("goal") or user_prompt[:80]
        subtasks = data.get("subtasks") or [user_prompt]
        assertions = data.get("assertions") or []

        return {
            "url": url,
            "goal": goal,
            "subtasks": subtasks,
            "assertions": assertions,
        }
