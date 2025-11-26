# src/oracle/assertions.py

import re
from typing import Any

from src.models.vlm_client import VLMClient


class Oracle:
    """
    Oracle that can evaluate assertions using:
    - DOM-based heuristics (when possible / reliable),
    - Visual checks via a VLM (Screenshot + text instruction).

    It is written to be *generic* and reusable across sites/apps:
    - No hardcoded selectors for a specific product/site.
    - Uses common patterns like "cart/basket/bag/checkout" in URLs/headings.
    """

    def __init__(self, vlm: VLMClient, browser: Any):
        self.vlm = vlm
        # browser is a src.browser.playwright_driver.Browser instance
        # We keep the type as Any to avoid circular imports.
        self.browser = browser

    # ---------- Public API ----------

    def check_assertion(self, screenshot_path: str, assertion: str) -> bool:
        """
        Check a single assertion against the current UI.

        Tries specialized DOM-aware checks first (for some assertions),
        falls back to visual/VLM-based checking otherwise.
        """
        assertion_l = assertion.lower()

        # Special handling: "The cart contains exactly X item(s)"
        # Accept both digits ("1") and small number words ("zero", "one", ...).
        m = re.search(r"cart\s+contains\s+exactly\s+(\w+)\s+item", assertion_l)
        if m:
            token = m.group(1).strip()
            expected = self._parse_number_token(token)
            if expected is not None:
                return self._check_cart_item_count(expected, screenshot_path, assertion)

        # Default: pure visual check via VLM
        return self._check_visual_assertion(screenshot_path, assertion)

    # ---------- Helpers ----------

    def _parse_number_token(self, token: str) -> int | None:
        """
        Convert a token like '0', '1', or 'zero', 'one' into an integer, if possible.
        """
        token = token.lower().strip()
        if token.isdigit():
            return int(token)

        words_map = {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
        }
        return words_map.get(token)

    # ---------- DOM-based cart checks ----------

    def _check_cart_item_count(self, expected: int, screenshot_path: str, assertion: str) -> bool:
        """
        Try to determine the number of items in the cart using DOM heuristics.
        If that fails, fall back to visual assertion via VLM.

        This is designed to be generic (not tied to a single site):
        - Tries common "cart item" patterns in classes/data attributes.
        - Tries a generic cart badge.
        - If we are clearly on a cart/basket/bag/checkout page and find no items,
          we infer that the cart count is 0.
        """
        page = self.browser.page
        count: int | None = None

        # Heuristic 1: elements that look like "cart items".
        # These selectors are generic but will also work on saucedemo and similar UIs.
        try:
            selectors = [
                ".cart_item",                # common pattern (e.g. saucedemo)
                "[class*='cart-item']",      # generic BEM-ish or utility classes
                "[data-test*='cart-item']",  # generic test-data hooks
            ]
            for sel in selectors:
                try:
                    loc = page.locator(sel)
                    c = loc.count()
                    if c > 0:
                        count = c
                        print(f"[ORACLE] Cart item count from DOM via selector {sel!r}: {c}")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[ORACLE] Error counting cart items by selector: {e}")

        # Heuristic 2: cart badge number (e.g. "1" in a cart icon badge)
        if count is None:
            try:
                badge = page.query_selector(".shopping_cart_badge, [class*='cart-badge']")
                if badge:
                    txt = (badge.inner_text() or "").strip()
                    if txt.isdigit():
                        count = int(txt)
                        print(f"[ORACLE] Cart item count from DOM badge: {count}")
            except Exception as e:
                print(f"[ORACLE] Error reading cart badge: {e}")

        # If we have a concrete count from DOM, compare and return.
        if count is not None:
            result = (count == expected)
            print(f"[ORACLE] Cart count comparison: expected={expected}, actual={count}, result={result}")
            return result

        # NEW: If we are clearly on a cart/basket/bag/checkout-like page and
        # did not find any cart items or badge, interpret that as "0 items".
        # This avoids relying on the VLM for the simplest case (empty cart),
        # and is generic enough to work across many sites.
        try:
            url = page.url or ""
            if re.search(r"cart|basket|bag|checkout|trolley", url, re.I):
                print("[ORACLE] No cart items/badge found on cart-like page; assuming count = 0")
                count = 0
                result = (count == expected)
                print(
                    f"[ORACLE] Cart count comparison (empty cart inference): "
                    f"expected={expected}, actual={count}, result={result}"
                )
                return result
        except Exception as e:
            print(f"[ORACLE] Error inferring empty cart from URL: {e}")

        # If all DOM methods fail, fall back to visual/VLM-based check.
        print("[ORACLE] Cart count DOM heuristics failed; falling back to visual check")
        return self._check_visual_assertion(screenshot_path, assertion)

    # ---------- Visual check via VLM ----------

    def _check_visual_assertion(self, screenshot_path: str, assertion: str) -> bool:
        """
        Ask the VLM to judge the assertion based on the screenshot.
        Expects a strict PASS/FAIL answer.
        """
        prompt = f"""
You are a precise UI testing oracle.

You are given:
- A screenshot of a web application's current state.
- A textual assertion about that UI state.

ASSERTION:
"{assertion}"

TASK:
- Look carefully at the screenshot.
- Decide whether the assertion is TRUE (PASS) or FALSE (FAIL).

RULES:
- If you are confident the assertion is correct, answer exactly: PASS
- If the assertion is not correct, or you are unsure, answer exactly: FAIL
- Do NOT include any explanation or extra text.
Just output one word: PASS or FAIL.
""".strip()

        raw = self.vlm.analyze(screenshot_path, prompt)
        if raw is None:
            print("[ORACLE] VLM returned None, treating as FAIL")
            return False

        val = raw.strip().upper()
        print(f"[ORACLE] Raw VLM assertion output: {val!r}")
        return val.startswith("PASS")
