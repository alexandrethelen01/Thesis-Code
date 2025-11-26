# src/main.py

import json
from datetime import datetime, timezone

from dotenv import load_dotenv

from src.config import LOGS_DIR, TEXT_LLM_MODEL_NAME, VLM_MODEL_NAME, DEVICE
from src.browser.playwright_driver import Browser
from src.models.llm_client import LLMClient
from src.models.vlm_client import VLMClient
from src.scenario.scenario_generator import ScenarioGenerator
from src.agent.agent import Agent
from src.oracle.assertions import Oracle

# Load .env so OPENAI_API_KEY is available before any OpenAI client is created
load_dotenv()


def main():
    print("Describe the test you want to run (plain English):")
    user_prompt = input("> ").strip()

    # 1. Setup models (OpenAI)
    llm = LLMClient(model_name=TEXT_LLM_MODEL_NAME)
    vlm = VLMClient(model_name=VLM_MODEL_NAME, device=DEVICE)

    # 2. Generate structured scenario
    scenario_gen = ScenarioGenerator(llm)
    scenario = scenario_gen.parse_prompt(user_prompt)

    url = scenario["url"]
    goal = scenario["goal"]
    subtasks = scenario["subtasks"]
    assertions = scenario["assertions"]

    print("\nGenerated scenario:")
    print(json.dumps(scenario, indent=2, ensure_ascii=False))

    # 3. Setup browser + agent + oracle
    browser = Browser()

    # 🔧 FIX: pass `browser` into Oracle, as required by its __init__ signature
    oracle = Oracle(vlm=vlm, browser=browser)

    agent = Agent(browser=browser, vlm=vlm, oracle=oracle)

    try:
        result = agent.run_scenario(
            url=url,
            goal=goal,
            subtasks=subtasks,
            assertions=assertions,
        )
    finally:
        browser.close()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"run_{ts}.json"
    log_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nRun finished. Status: {result['status']}")
    print(f"Log written to: {log_path}")


if __name__ == "__main__":
    main()
