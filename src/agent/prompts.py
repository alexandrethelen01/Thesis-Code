# src/agent/prompts.py
from typing import List

from src.config import VIEWPORT_WIDTH, VIEWPORT_HEIGHT


def build_action_prompt(goal: str, subtask: str, history: List[str]) -> str:
    history_text = "\n".join(history[-4:]) or "No previous actions."

    return f"""
You are a UI testing agent controlling a web browser using a combination of
semantic hints and pixel coordinates.

SCREEN:
- The screenshot shows the current browser viewport.
- Coordinate system: x in [0, {VIEWPORT_WIDTH-1}], y in [0, {VIEWPORT_HEIGHT-1}].
- (0,0) is top-left.

OVERALL TEST GOAL:
{goal}

CURRENT SUBTASK:
{subtask}

RECENT ACTION HISTORY:
{history_text}

You must choose EXACTLY ONE next action that moves toward completing the CURRENT SUBTASK.

Valid actions (JSON):

1) Click:
{{
  "action_type": "click",
  "x": <int>,          // approximate click x coordinate
  "y": <int>,          // approximate click y coordinate
  "text": "",
  "target_hint": "<short phrase describing the target, e.g. 'login button', 'username field', 'shopping cart icon'>",
  "reason": "<short reason>"
}}

2) Type (click then type):
{{
  "action_type": "type",
  "x": <int>,
  "y": <int>,
  "text": "<text to type>",
  "target_hint": "<short phrase describing where the text should go, e.g. 'username field', 'password field', 'search box'>",
  "reason": "<short reason>"
}}

3) Scroll:
{{
  "action_type": "scroll",
  "x": 0,
  "y": 0,
  "text": "<integer pixels to scroll, positive down, negative up>",
  "target_hint": "viewport",
  "reason": "<short reason>"
}}

4) Done with this subtask:
{{
  "action_type": "done",
  "x": 0,
  "y": 0,
  "text": "",
  "target_hint": "",
  "reason": "<short reason>"
}}

5) Error:
{{
  "action_type": "error",
  "x": 0,
  "y": 0,
  "text": "",
  "target_hint": "",
  "reason": "<short description of why>"
}}

Rules:
- Output ONLY a valid JSON object with the keys: action_type, x, y, text, target_hint, reason.
- Do NOT include any extra text or markdown.
- Coordinates should be a reasonable approximation of the target location.
- target_hint is REQUIRED and should be a short semantic description of the UI element:
  - Examples: "username field", "password field", "login button",
    "add to cart button", "search box", "menu button", "shopping cart icon".
"""
