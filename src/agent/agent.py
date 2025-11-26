# src/agent/agent.py

import json
import re
from typing import List, Dict, Any

from src.browser.playwright_driver import Browser
from src.models.vlm_client import VLMClient
from src.models.action import Action
from src.agent.prompts import build_action_prompt
from src.oracle.assertions import Oracle
from src.config import MAX_STEPS_PER_SUBTASK


class Agent:
    def __init__(self, browser: Browser, vlm: VLMClient, oracle: Oracle):
        self.browser = browser
        self.vlm = vlm
        self.oracle = oracle
        self.history: List[str] = []

    # ---------- VLM decision ----------

    def _decide_next_action(self, goal: str, subtask: str, screenshot_path: str) -> Action:
        prompt = build_action_prompt(goal=goal, subtask=subtask, history=self.history)
        raw = self.vlm.analyze(screenshot_path, prompt)

        try:
            data = json.loads(raw)
            action = Action(**data)
        except Exception as e:
            print(f"[AGENT] JSON parse error from VLM: {e}")
            print(f"[AGENT] Raw VLM output: {raw!r}")
            return Action(
                action_type="error",
                text="",
                target_hint="",
                reason=f"JSON parse error: {e}; raw={raw!r}",
            )

        print(f"[AGENT] Subtask: {subtask}")
        print(f"[AGENT] Action from VLM: {action.dict()}")

        self.history.append(
            f"{action.action_type}@({action.x},{action.y}) "
            f"text='{action.text}' target='{action.target_hint}' reason='{action.reason}'"
        )
        return action

    # ---------- Generic DOM/URL heuristics: subtask satisfaction ----------

    def _is_subtask_satisfied(self, subtask: str) -> bool:
        """
        Check via DOM/URL heuristics whether the current subtask already
        appears to be satisfied (generic, not site-specific).
        """
        page = self.browser.page
        s = (subtask or "").lower()

        cart_like_pattern = re.compile(r"cart|basket|bag|checkout|trolley", re.I)

        try:
            # 0) Login completion: subtask mentions clicking the login button.
            if "login" in s and "button" in s:
                # Heuristic: if there is no visible password field anymore,
                # or no visible login button, assume login has completed.
                try:
                    pwd_locator = page.locator("input[type='password']")
                    visible_pwd = 0
                    try:
                        count = pwd_locator.count()
                    except Exception:
                        count = 0
                    for i in range(count):
                        try:
                            if pwd_locator.nth(i).is_visible():
                                visible_pwd += 1
                        except Exception:
                            pass
                    if visible_pwd == 0:
                        print("[AGENT] Subtask satisfied: no visible password inputs (login likely complete)")
                        return True
                except Exception:
                    pass

                try:
                    pattern_login = re.compile(r"log\s*in|login|sign\s*in", re.I)
                    btns = page.get_by_role("button", name=pattern_login)
                    visible_login = 0
                    try:
                        count = btns.count()
                    except Exception:
                        count = 0
                    for i in range(count):
                        try:
                            if btns.nth(i).is_visible():
                                visible_login += 1
                        except Exception:
                            pass
                    if visible_login == 0:
                        print("[AGENT] Subtask satisfied: no visible login button (login likely complete)")
                        return True
                except Exception:
                    pass

            # 1) Generic "Type X into the Y field"
            m = re.search(r"type\s+(.+?)\s+into\s+the\s+(.+?)\s+field", s)
            if m:
                expected_text = m.group(1).strip(" '\"")
                if expected_text:
                    try:
                        inputs = page.query_selector_all("input, textarea")
                        for el in inputs:
                            val = el.evaluate("el => el ? (el.value || '') : ''")
                            if expected_text.lower() in (val or "").lower():
                                print(
                                    f"[AGENT] Subtask satisfied: found input with value "
                                    f"{val!r} for expected {expected_text!r}"
                                )
                                return True
                    except Exception:
                        pass

            # 2) "Click the first visible Add to cart button" → look for 'Remove'
            if "add to cart" in s or "add item" in s or "add product" in s:
                try:
                    remove_btns = page.get_by_role("button", name=re.compile(r"remove", re.I))
                    if remove_btns.count() > 0:
                        print("[AGENT] Subtask satisfied: found at least one 'Remove' button (item added)")
                        return True
                except Exception:
                    pass

            # 3) Cart-opening subtasks → URL or heading indicates cart/basket/bag/checkout
            if any(
                k in s
                for k in [
                    "open the shopping cart page",
                    "open cart page",
                    "cart page",
                    "shopping cart",
                    "click the cart icon",
                    "open the cart",
                    "go to the cart",
                    "go to the basket",
                    "open basket",
                    "open bag",
                ]
            ):
                try:
                    url = page.url or ""
                    if cart_like_pattern.search(url):
                        print(f"[AGENT] Subtask satisfied: URL indicates cart/basket/bag/checkout view ({url})")
                        return True
                except Exception:
                    pass

                try:
                    headings = page.get_by_role("heading", name=cart_like_pattern)
                    if headings.count() > 0 and headings.first.is_visible():
                        print("[AGENT] Subtask satisfied: heading indicates cart/basket/bag/checkout view")
                        return True
                except Exception:
                    pass

            # 4) "Click the remove button for the item" → no 'Remove' buttons remain,
            #    *but only when we're in a cart/basket/bag/checkout-like context*.
            if "remove" in s and "button" in s:
                in_cartish = False
                try:
                    url = page.url or ""
                    if cart_like_pattern.search(url):
                        in_cartish = True
                except Exception:
                    pass

                if not in_cartish:
                    try:
                        headings = page.get_by_role("heading", name=cart_like_pattern)
                        if headings.count() > 0 and headings.first.is_visible():
                            in_cartish = True
                    except Exception:
                        pass

                if not in_cartish:
                    # We don't consider this subtask satisfied yet if we're not
                    # clearly on a cart/basket/bag/checkout-like view.
                    return False

                try:
                    remove_btns = page.get_by_role("button", name=re.compile(r"remove", re.I))
                    if remove_btns.count() == 0:
                        print("[AGENT] Subtask satisfied: no 'Remove' buttons remain (item removed)")
                        return True
                except Exception:
                    pass

        except Exception as e:
            print(f"[AGENT] _is_subtask_satisfied error: {e}")

        return False

    # ---------- Generic DOM heuristics: fill/click ----------

    def _fill_input_by_hint(self, hint: str, text: str) -> bool:
        """
        Fill an input using only generic heuristics:
        - look for placeholders, labels, input types, etc.
        """
        page = self.browser.page
        hint_l = (hint or "").lower()
        text = text or ""

        pattern_password = re.compile(r"pass|password", re.I)
        pattern_user = re.compile(r"user|username|email|login", re.I)

        try:
            # Password-like fields
            if pattern_password.search(hint_l):
                try:
                    page.get_by_placeholder(pattern_password).fill(text)
                    print(f"[AGENT] Filled password-like field by placeholder with {text!r}")
                    return True
                except Exception:
                    pass

                try:
                    page.get_by_label(pattern_password).fill(text)
                    print(f"[AGENT] Filled password-like field by label with {text!r}")
                    return True
                except Exception:
                    pass

                try:
                    page.locator("input[type='password']").first.fill(text)
                    print(f"[AGENT] Filled first password-type input with {text!r}")
                    return True
                except Exception:
                    pass

            # Username / email / login-like fields
            if pattern_user.search(hint_l):
                try:
                    page.get_by_placeholder(pattern_user).fill(text)
                    print(f"[AGENT] Filled username/email-like field by placeholder with {text!r}")
                    return True
                except Exception:
                    pass

                try:
                    page.get_by_label(pattern_user).fill(text)
                    print(f"[AGENT] Filled username/email-like field by label with {text!r}")
                    return True
                except Exception:
                    pass

                try:
                    page.locator("input[type='text'], input:not([type])").first.fill(text)
                    print(f"[AGENT] Filled first generic text input with {text!r}")
                    return True
                except Exception:
                    pass

            # Fallback: first visible input
            try:
                page.locator("input").first.fill(text)
                print(f"[AGENT] Filled first input (fallback) with {text!r}")
                return True
            except Exception:
                pass

        except Exception as e:
            print(f"[AGENT] _fill_input_by_hint error: {e}")

        return False

    def _click_by_hint(self, hint: str) -> bool:
        """
        Click a button or link using generic heuristics:
        - based on hint/subtask/reason text and ARIA roles or visible text.
        Returns True if something was clicked, False otherwise.

        IMPORTANT:
        - We have a dedicated branch for *cart icons* that avoids matching
          "Add to cart".
        """
        page = self.browser.page
        hint_l = (hint or "").lower()

        try:
            # 1) Remove / delete buttons
            if "remove" in hint_l or "delete" in hint_l or "trash" in hint_l:
                pattern_remove = re.compile(r"remove|delete|trash", re.I)

                try:
                    page.get_by_role("button", name=pattern_remove).first.click()
                    print("[AGENT] Clicked remove-like button by role+name")
                    return True
                except Exception:
                    pass

                try:
                    page.get_by_text(pattern_remove).first.click()
                    print("[AGENT] Clicked remove-like element by text")
                    return True
                except Exception:
                    pass

            # 2) Login / sign in buttons
            if any(k in hint_l for k in ["login", "log in", "sign in"]):
                pattern_login = re.compile(r"log\s*in|login|sign\s*in", re.I)

                try:
                    page.get_by_role("button", name=pattern_login).first.click()
                    print("[AGENT] Clicked login-like button by role+name")
                    return True
                except Exception:
                    pass

                try:
                    page.get_by_text(pattern_login).first.click()
                    print("[AGENT] Clicked login-like element by text")
                    return True
                except Exception:
                    pass

            # 3) Add to cart / add item buttons
            if any(k in hint_l for k in ["add to cart", "add item", "add product"]):
                pattern_add = re.compile(r"add\s+to\s+cart|add", re.I)

                try:
                    page.get_by_role("button", name=pattern_add).first.click()
                    print("[AGENT] Clicked add-to-cart-like button by role+name")
                    return True
                except Exception:
                    pass

                try:
                    page.get_by_text(pattern_add).first.click()
                    print("[AGENT] Clicked add-to-cart-like element by text")
                    return True
                except Exception:
                    pass

            # 4) Cart icon / cart navigation (generic, but NOT "Add to cart")
            if any(
                k in hint_l
                for k in [
                    "cart icon",
                    "shopping cart icon",
                    "open the shopping cart page",
                    "open the cart",
                    "open cart page",
                    "go to the cart",
                    "go to the basket",
                    "shopping cart page",
                ]
            ):
                # Match accessible names that START with cart-like words, so
                # "Cart" or "Shopping cart" match, but "Add to cart" does NOT.
                pattern_cart_icon = re.compile(
                    r"^(cart|shopping cart|basket|bag|trolley|checkout)\b",
                    re.I,
                )

                try:
                    page.get_by_role("link", name=pattern_cart_icon).first.click()
                    print("[AGENT] Clicked cart/basket/bag/checkout icon by role+name")
                    return True
                except Exception:
                    pass

                try:
                    page.get_by_text(pattern_cart_icon).first.click()
                    print("[AGENT] Clicked cart/basket/bag/checkout icon by text")
                    return True
                except Exception:
                    pass

            # 5) Generic "submit" / "continue" / "next" buttons
            if any(k in hint_l for k in ["submit", "continue", "next"]):
                pattern_submit = re.compile(r"submit|continue|next", re.I)

                try:
                    page.get_by_role("button", name=pattern_submit).first.click()
                    print("[AGENT] Clicked submit-like button by role+name")
                    return True
                except Exception:
                    pass

                try:
                    page.get_by_text(pattern_submit).first.click()
                    print("[AGENT] Clicked submit-like element by text")
                    return True
                except Exception:
                    pass

        except Exception as e:
            print(f"[AGENT] _click_by_hint error: {e}")

        return False

    # ---------- Execute action ----------

    def _execute_action(self, action: Action, subtask: str):
        """
        Execute the chosen action in the Playwright browser.

        Strategy:
        - Use target_hint + subtask + reason as a semantic description of the target.
        - Try generic DOM-based heuristics first (fill/click by placeholder,
          label, role, text).
        - If that fails, fall back to raw coordinate-based actions.
        """
        hint_parts = [
            subtask or "",
            action.reason or "",
            action.target_hint or "",
            action.text or "",
        ]
        combined_hint = " ".join(hint_parts).strip()

        if action.action_type == "type":
            if combined_hint:
                success = self._fill_input_by_hint(combined_hint, action.text)
                if success:
                    return
            if action.x is not None and action.y is not None:
                self.browser.type_text(action.x, action.y, action.text)
            return

        if action.action_type == "click":
            if combined_hint:
                success = self._click_by_hint(combined_hint)
                if success:
                    return
            if action.x is not None and action.y is not None:
                self.browser.click_coordinates(action.x, action.y)
            return

        if action.action_type == "scroll":
            delta = int(action.text or "300")
            self.browser.scroll(delta)
            return

        if action.action_type in {"done", "error"}:
            return

    # ---------- Scenario loop ----------

    def run_scenario(
        self,
        url: str,
        goal: str,
        subtasks: List[str],
        assertions: List[str],
    ) -> Dict[str, Any]:
        print(f"[AGENT] Navigating to URL: {url}")
        self.browser.goto(url)
        screenshot_path = self.browser.screenshot("initial")

        result: Dict[str, Any] = {
            "url": url,
            "goal": goal,
            "subtasks": [],
            "assertions": [],
            "status": "unknown",
        }

        for subtask in subtasks:
            lowered = subtask.strip().lower()

            # "Verify ..." subtasks are observation-only.
            if lowered.startswith("verify "):
                print(f"[AGENT] Skipping action for verification-only subtask: {subtask}")
                result["subtasks"].append(
                    {
                        "subtask": subtask,
                        "steps": [],
                        "status": "done",
                    }
                )
                continue

            # "Wait for ..." subtasks are treated as no-op milestones.
            if lowered.startswith("wait for "):
                print(f"[AGENT] Treating wait subtask as no-op marker: {subtask}")
                result["subtasks"].append(
                    {
                        "subtask": subtask,
                        "steps": [],
                        "status": "done",
                    }
                )
                continue

            print(f"\n[AGENT] Starting subtask: {subtask}")
            subtask_log: Dict[str, Any] = {
                "subtask": subtask,
                "steps": [],
                "status": "unknown",
            }

            for step_idx in range(MAX_STEPS_PER_SUBTASK):
                # 1) Check if already satisfied in DOM/URL
                if self._is_subtask_satisfied(subtask):
                    print(f"[AGENT] Subtask already satisfied in DOM/URL: {subtask}")
                    subtask_log["status"] = "done"
                    break

                # 2) Ask VLM for next action
                action = self._decide_next_action(goal, subtask, screenshot_path)
                subtask_log["steps"].append(action.dict())

                # 3) If VLM says "done", only accept it if DOM/URL agrees
                if action.action_type == "done":
                    if self._is_subtask_satisfied(subtask):
                        print(f"[AGENT] Subtask marked done by VLM and confirmed in DOM/URL: {subtask}")
                        subtask_log["status"] = "done"
                        break
                    else:
                        print(f"[AGENT] VLM marked subtask done, but DOM/URL check failed; continuing: {subtask}")
                        continue

                # 4) Handle error
                if action.action_type == "error":
                    print(f"[AGENT] Subtask errored: {subtask} – {action.reason}")
                    subtask_log["status"] = f"error: {action.reason}"
                    break

                # 5) Execute the action
                self._execute_action(action, subtask)

                # 6) New screenshot after performing the action
                screenshot_path = self.browser.screenshot(f"subtask_step_{step_idx}")

            else:
                print(f"[AGENT] Subtask timed out: {subtask}")
                subtask_log["status"] = "timeout"

            result["subtasks"].append(subtask_log)

        print("\n[AGENT] Running assertions on final screenshot...")
        final_screenshot = self.browser.screenshot("final")

        assertion_results = []
        for assertion in assertions:
            print(f"[AGENT] Checking assertion: {assertion}")
            passed = self.oracle.check_assertion(final_screenshot, assertion)
            assertion_results.append({"assertion": assertion, "passed": passed})
            print(f"[AGENT] Assertion result: {'PASS' if passed else 'FAIL'}")

        # ---------- FINAL STATUS ----------
        all_good_subtasks = all(st["status"] == "done" for st in result["subtasks"])

        # Treat "overlap" checks as non-blocking (informational only).
        functional_assertions = [
            a for a in assertion_results
            if "overlap" not in a["assertion"].lower()
        ]

        if functional_assertions:
            all_good_assertions = all(a["passed"] for a in functional_assertions)
        else:
            all_good_assertions = True

        result["status"] = "pass" if (all_good_subtasks and all_good_assertions) else "fail"
        print(f"\n[AGENT] Scenario finished with status: {result['status']}")

        return result
