# src/models/action.py
from typing import Literal, Optional
from pydantic import BaseModel


ActionType = Literal["click", "type", "scroll", "assert", "done", "error"]


class Action(BaseModel):
    action_type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: str = ""
    # NEW: semantic hint, e.g. "username field", "password field", "login button"
    target_hint: str = ""
    reason: str = ""
