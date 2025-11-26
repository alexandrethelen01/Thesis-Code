# src/config.py
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
SCREENSHOTS_DIR = ARTIFACTS_DIR / "screenshots"
LOGS_DIR = BASE_DIR / "logs"

# Ensure dirs exist
for d in (ARTIFACTS_DIR, SCREENSHOTS_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# App / test defaults
# You can change this, but most of the time your prompt will specify a URL.
DEFAULT_URL = "www.saucedemo.com"

# Browser settings
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
# Keep headless False while you’re developing so you SEE what happens.
HEADLESS = False

# Agent settings
MAX_STEPS_PER_SUBTASK = 8

# Model configuration (OpenAI)
TEXT_LLM_MODEL_NAME = "gpt-4o-mini"
VLM_MODEL_NAME = "gpt-4o-mini"
DEVICE = "cpu"
