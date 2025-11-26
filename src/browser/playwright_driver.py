# src/browser/playwright_driver.py

from datetime import datetime

from playwright.sync_api import sync_playwright, Page

from src.config import (
    SCREENSHOTS_DIR,
    VIEWPORT_WIDTH,
    VIEWPORT_HEIGHT,
    HEADLESS,
)


class Browser:
    def __init__(self, headless: bool = HEADLESS):
        self._p = sync_playwright().start()

        # Launch Chromium with explicit viewport and scale
        self._browser = self._p.chromium.launch(headless=headless)
        self._context = self._browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            device_scale_factor=1,  # 1 CSS pixel = 1 screenshot pixel
        )
        self.page: Page = self._context.new_page()

    def goto(self, url: str):
        print(f"[BROWSER] Goto: {url}")
        self.page.goto(url, wait_until="networkidle")

    def screenshot(self, label: str) -> str:
        """
        Screenshot of the viewport only (not full page),
        so coordinates match the VIEWPORT_WIDTH x VIEWPORT_HEIGHT grid.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        safe_label = "".join(c for c in label if c.isalnum() or c in ("-", "_"))
        filename = f"{timestamp}_{safe_label}.png"
        path = SCREENSHOTS_DIR / filename

        # No full_page=True: just the viewport
        self.page.screenshot(path=str(path))
        print(f"[BROWSER] Screenshot saved: {path}")
        return str(path)

    # ---------- Generic coordinate actions ----------

    def click_coordinates(self, x: int, y: int):
        print(f"[BROWSER] Clicking at ({x}, {y})")
        self.page.mouse.click(x, y)

    def type_text(self, x: int, y: int, text: str):
        print(f"[BROWSER] Typing at ({x}, {y}): {text!r}")
        self.page.mouse.click(x, y)
        # Give the browser a tiny moment to focus the input
        self.page.wait_for_timeout(50)
        self.page.keyboard.type(text, delay=20)

    def scroll(self, delta_y: int):
        print(f"[BROWSER] Scrolling by {delta_y} pixels")
        self.page.mouse.wheel(0, delta_y)

    def wait(self, seconds: float):
        print(f"[BROWSER] Waiting for {seconds} seconds")
        self.page.wait_for_timeout(int(seconds * 1000))

    def close(self):
        self._context.close()
        self._browser.close()
        self._p.stop()
