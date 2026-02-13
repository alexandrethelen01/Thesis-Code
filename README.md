# Natural-Language Visual UI Test Runner (Thesis Prototype)

This repository contains a research prototype for **natural-language–driven, visual UI testing** using **Playwright**, a **text LLM**, and a **vision-language model (VLM)**.

At a high level:

* You type a **plain English description** of the test you want (e.g. full login + cart flow).
* The system turns this into a **structured scenario** (URL, subtasks, assertions).
* An **agent** uses Playwright + a VLM to:

  * Navigate the page,
  * Decide what to click/type/scroll based on screenshots of the current UI, and
  * Evaluate **visual assertions** (e.g. cart contents, overlap checks) from a final screenshot and DOM heuristics.
* The run is logged to JSON and screenshots are saved for inspection.

---

## 1. Project Overview

This prototype is a **CLI application** (run from the terminal) that:

1. Prompts the tester for a **natural language test description**.
2. Uses a text LLM to generate a **scenario JSON** with:

   * `url`
   * `goal`
   * `subtasks` (step-by-step actions like “Click the Login button”)
   * `assertions` (e.g. “The cart contains exactly zero items”)
3. Drives a real browser via **Playwright**:

   * Each subtask is executed by an **Agent** that:

     * Observes a screenshot,
     * Asks the VLM what to do next (`click`, `type`, `scroll`, `done`, etc.),
     * Applies **generic DOM heuristics** (selectors, roles, text locators) to perform actions on **any web app**.
4. Evaluates assertions with an **Oracle**:

   * Uses DOM-based heuristics where possible (e.g. cart item count).
   * Otherwise, uses the VLM to judge a screenshot as **PASS/FAIL** for a given assertion.

Artifacts created per run:

* **Screenshots** under `artifacts/screenshots/`
* **JSON log** per run under `logs/run_YYYYMMDD_HHMMSS.json`

The architecture is deliberately **website-agnostic**; all clicking/typing logic is phrased in terms of:

* ARIA roles,
* visible text / labels,
* generic selectors (no hardcoded `saucedemo` locators).

---

## 2. Setup Instructions (New Machine)

### 2.1 Prerequisites

* **Python** 3.10+ (the project was developed with Python 3.x)
* **Git**
* Ability to install Python packages and Playwright browsers

### 2.2 Clone the Repository

```bash
git clone <YOUR_REPO_URL> thesis-ui-test-runner
cd thesis-ui-test-runner
```

### 2.3 Create and Activate a Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux (bash/zsh):**

```bash
python -m venv .venv
source .venv/bin/activate
```

You should now see `(.venv)` in your prompt.

### 2.4 Install Python Dependencies

Assuming there is a `requirements.txt` in the repo:

```bash
pip install -r requirements.txt
```

(This will install Playwright, OpenAI client, python-dotenv, and other required libraries.)

### 2.5 Install Playwright Browsers

Playwright needs to download browser binaries:

```bash
playwright install
```

### 2.6 Configure API Keys

The app uses environment variables via `python-dotenv` (`load_dotenv()` in `src/main.py`).

Create a `.env` file in the project root:

```bash
# .env
OPENAI_API_KEY=sk-...
```

(Replace `sk-...` with your real key.)

> ⚠️ Do **not** commit `.env` to Git if this is a public repository.

### 2.7 (Optional) Model Configuration

Model names are defined in `src/config.py`:

```python
TEXT_LLM_MODEL_NAME = "..."
VLM_MODEL_NAME = "..."
```

If needed, adjust these to the exact models you want to use (e.g. from OpenAI).
The rest of the code reads these constants and does not hard-code any model IDs.

---

## 3. Running the App

With your virtual environment active and dependencies installed:

```bash
python -m src.main
```

You should see:

```text
Describe the test you want to run (plain English):
>
```

At this prompt, you enter your test description as one long sentence or paragraph.

---

## 4. Example: Using the App with a Full Scenario

Here is the exact **example prompt** that we’ve been using throughout the project (you can copy-paste this):

```text
Go to https://www.saucedemo.com, log in using the username "standard_user" and the password "secret_sauce", wait for the products page to load, click the first visible "Add to cart" button to add one item, then click the cart icon to open the shopping cart page, on the cart page click the "Remove" button to remove that item from the cart, and verify that at the end of the test the cart contains exactly zero items and that no UI elements overlap on the screen.
```

### 4.1 What Happens Step-by-Step

1. **You type the prompt** (as above) after the `>` in the terminal and press Enter.

2. The text LLM generates a structured **scenario** like:

   ```json
   {
     "url": "https://www.saucedemo.com",
     "goal": "Test item addition and removal from the shopping cart",
     "subtasks": [
       "Type standard_user into the username field",
       "Type secret_sauce into the password field",
       "Click the Login button",
       "Wait for the products page to load",
       "Click the first visible Add to cart button",
       "Click the cart icon to open the shopping cart page",
       "Click the Remove button to remove the item from the cart"
     ],
     "assertions": [
       "The cart contains exactly zero items",
       "No UI elements overlap on the screen"
     ]
   }
   ```

   This JSON is printed to the console for transparency.

3. The **Agent** then:

   * Opens a browser and navigates to `https://www.saucedemo.com`.
   * For each subtask:

     * Takes a screenshot of the current page.
     * Calls the VLM with a prompt: “Given this screenshot and the current subtask, what action should I take?”
     * Parses the VLM’s JSON action (e.g. `{"action_type": "click", "x": 310, "y": 350, ...}`).
     * Uses **generic DOM heuristics** to perform that action:

       * For typing:

         * Uses placeholders / labels / `input[type=password]` vs `input[type=text]`.
       * For clicks:

         * Uses roles (`get_by_role("button", name=...)`),
         * Visible text (`get_by_text(...)`),
         * Cart-like names (`"cart"`, `"basket"`, `"bag"`, but **not** “Add to cart”).
       * Falls back to coordinate-based clicking only if needed.
     * Logs each action and saves a screenshot.

4. After all subtasks, the **Oracle**:

   * Captures a final screenshot.
   * Evaluates each assertion:

     * For “The cart contains exactly zero items”:

       * Tries DOM heuristics (cart row selectors, cart badges).
       * If DOM heuristics fail, asks the VLM:

         * “Given this screenshot, is the statement ‘The cart contains exactly zero items’ PASS or FAIL?”
     * For “No UI elements overlap on the screen”:

       * Directly uses the VLM as a visual oracle.

5. The application outputs:

   * Subtask statuses: `done`, `timeout`, or `error: ...`
   * Assertion results: `PASS` / `FAIL`
   * Run status: `pass` or `fail` at the end.

6. A JSON log is written, e.g.:

   ```text
   logs/run_20251126_204954.json
   ```

   And all screenshots for that run are stored under:

   ```text
   artifacts/screenshots/
   ```

---

## 5. How the System Works (Technical Summary)

### 5.1 High-Level Architecture

* **CLI entry point**: `src/main.py`
* **Text LLM client**: `src/models/llm_client.py`
* **VLM client**: `src/models/vlm_client.py`
* **Scenario generation**: `src/scenario/scenario_generator.py`
* **Agent (test executor)**: `src/agent/agent.py`
* **Action prompt templates**: `src/agent/prompts.py`
* **Playwright wrapper**: `src/browser/playwright_driver.py`
* **Oracle (assertion engine)**: `src/oracle/assertions.py`
* **Config & paths**: `src/config.py`

### 5.2 Natural Language → Scenario

`ScenarioGenerator` takes the raw user prompt and uses the text LLM to:

* Extract a canonical `url`.
* Derive a `goal` string.
* Decompose the description into ordered, concrete `subtasks`.
* Derive textual `assertions` that can later be evaluated visually or via DOM.

The scenario format is JSON-like and **model-agnostic**, so it can be reused for other runners.

### 5.3 Scenario → Playwright Actions

The `Agent` receives:

* The `Browser` instance (Playwright driver).
* The VLM client.
* The `Oracle`.

For each subtask:

1. It first calls `_is_subtask_satisfied(subtask)`:

   * Checks DOM/URL heuristics, e.g.:

     * Is a specific value already present in an input?
     * Are there any “Remove” buttons visible after an “Add to cart” subtask?
     * Does the current URL indicate a cart/checkout/basket page?
     * If we’re on a cart-like page, have all “Remove” buttons disappeared?

2. If not satisfied, it takes a screenshot and calls `_decide_next_action(...)`:

   * Builds a structured prompt with:

     * The overall goal.
     * The current subtask.
     * A short history of previous actions.
   * Sends the screenshot + prompt to the VLM.
   * Parses the returned JSON into an `Action` object:

     * `action_type`: `click`, `type`, `scroll`, `done`, `error`
     * `x`, `y`: coordinates (optional)
     * `text`: e.g. text to type or scroll delta
     * `target_hint`: natural language hint of what to interact with
     * `reason`: natural language explanation from the VLM

3. `_execute_action(action, subtask)` then:

   * Builds a **combined semantic hint** from:

     * Subtask text,
     * VLM `reason`,
     * `target_hint`,
     * `text`.
   * For `type`:

     * Attempts to locate inputs via placeholder, label, or type (`password` vs text).
   * For `click`:

     * Prioritizes semantic matching first:

       * Remove / delete / trash buttons
       * Login / sign-in buttons
       * Add-to-cart buttons
       * Cart/basket/bag/checkout icons
       * Generic submit / continue / next
     * Only falls back to coordinate click when all semantic strategies fail.
   * For `scroll`:

     * Converts the VLM’s textual scroll amount into an integer delta.

4. After each action, a new screenshot is taken for the next decision step.

### 5.4 Assertions and Visual Oracle

The `Oracle` supports two main strategies:

1. **DOM-based heuristics** (where possible):

   * Example: cart item count

     * Looks for elements matching selectors like:

       * `.cart_item`
       * `[class*='cart-item']`
       * `[data-test*='cart-item']`
     * Or a badge:

       * `.shopping_cart_badge`
       * `[class*='cart-badge']`
     * If a count can be computed reliably, it is compared to the expected number.

2. **Visual checks via VLM**:

   * Generic prompt:

     * “Given this screenshot and this assertion string, respond only with PASS or FAIL.”
   * Used for:

     * When DOM heuristics fail.
     * UI overlap checks (“No UI elements overlap on the screen”).
     * Any other purely visual assertion strings.

The Oracle abstracts away whether a check is DOM- or screenshot-based; tests are defined only in terms of **natural language assertions**.

---

## 6. Notes and Limitations

* The system is a **research prototype**, not a production testing framework.
* Behavior depends heavily on:

  * The quality of the LLM/VLM,
  * The clarity of the natural language prompt,
  * The structure/accessibility of the target web app.
* Tests are **best-effort**:

  * The agent may occasionally mis-click or misinterpret a subtask.
  * Visual assertions rely on the VLM’s perception.

---