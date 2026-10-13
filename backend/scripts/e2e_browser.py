"""Browser end-to-end test with Playwright.

Starts the backend (uvicorn) and the built frontend (vite preview), then
drives a real Chromium session through the main business flow:

    login -> dashboard -> record a sale -> cancel it -> viewer role limits

Usage (from backend/, after `npm run build` in frontend/):

    .venv/bin/pip install playwright
    .venv/bin/playwright install chromium
    .venv/bin/python scripts/e2e_browser.py
"""

import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
API_PORT = 8000
WEB_PORT = 4173


def wait_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"port {port} did not open in time")


def wait_http(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"{url} did not respond in time")


def start(cmd, cwd: Path, env=None) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def backend_env() -> dict:
    import os

    env = dict(os.environ)
    env["CORS_ORIGINS"] = (
        f"http://127.0.0.1:{WEB_PORT},http://localhost:{WEB_PORT}"
    )
    return env


def main() -> int:
    from playwright.sync_api import sync_playwright

    backend = start(
        [str(BACKEND_DIR / ".venv/bin/uvicorn"), "app.main:app",
         "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=BACKEND_DIR,
        env=backend_env(),
    )
    web = start(
        ["npm", "run", "preview", "--", "--port", str(WEB_PORT), "--strictPort"],
        cwd=FRONTEND_DIR,
    )

    failures: list[str] = []

    try:
        wait_port(API_PORT)
        wait_http(f"http://127.0.0.1:{API_PORT}/health")
        wait_http(f"http://127.0.0.1:{WEB_PORT}/")

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            base = f"http://127.0.0.1:{WEB_PORT}"

            # --- Login ---------------------------------------------------
            page.goto(base)
            page.get_by_label("Username").fill("admin")
            page.get_by_label("Password").fill("HisabPro!2026")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_selector("text=Key metrics", timeout=15000)
            # The first metric starts at "0 g" until the fetch lands.
            page.wait_for_function(
                """() => {
                    const el = document.querySelector('.metric-card strong');
                    return el && !el.textContent.trim().startsWith('0');
                }""",
                timeout=15000,
            )
            print("PASS login -> dashboard")

            # Dashboard shows real stock numbers from the seeded database.
            stock = page.locator(".metric-card strong").first.inner_text()
            assert stock.strip() != "0 g", f"dashboard stock empty: {stock}"
            print(f"PASS dashboard shows live stock ({stock})")

            # --- Record a sale -------------------------------------------
            page.get_by_role("button", name="Sales").click()
            page.wait_for_selector("text=Record sale", timeout=10000)
            page.get_by_label("Product").select_option(label="Gold 24K bar (GOLD-24K)")
            page.get_by_label("Gross weight (g)").fill("2")
            page.get_by_label("Net weight (g)").fill("2")
            page.get_by_label("Amount paid now (PKR)").fill("0")
            page.get_by_role("button", name=re.compile("Save sale")).click()
            page.wait_for_selector("text=Transaction history", timeout=15000)
            print("PASS sale saved -> transaction history")

            # First row is the sale we just created.
            first_row = page.locator("tbody tr").first
            row_text = first_row.inner_text()
            assert "sale" in row_text.lower(), row_text
            first_row.get_by_text("Cancel", exact=True).click()
            page.wait_for_selector(".modal-heading h2", timeout=10000)
            modal_title = page.locator(".modal-heading h2").inner_text()
            assert modal_title.startswith("Cancel "), modal_title
            page.get_by_label("Reason (required)").fill("browser e2e cancel")
            page.get_by_role("button", name="Cancel transaction").click()
            page.wait_for_selector("text=cancel ho gayi", timeout=15000)

            # The cancelled row leaves the default "active" view (correct
            # behaviour); confirm it under the cancelled filter.
            page.get_by_role("combobox").nth(1).select_option("cancelled")
            page.wait_for_selector("tr:has-text('Cancelled')", timeout=10000)
            print("PASS sale cancelled with reversal (row kept, marked Cancelled)")

            # --- Reports -------------------------------------------------
            page.get_by_role("button", name="Reports").click()
            page.wait_for_selector("text=Outstanding amounts", timeout=10000)
            print("PASS reports page loads")

            # --- POS checkout -------------------------------------------
            page.get_by_role("button", name="POS").click()
            page.wait_for_selector("text=Point of sale", timeout=10000)
            page.get_by_placeholder("Type to find a product…").fill("GOLD-24K")
            page.wait_for_selector("tr:has-text('GOLD-24K')", timeout=10000)
            page.locator("tr", has_text="GOLD-24K").get_by_text(
                "Add", exact=True
            ).click()
            page.wait_for_selector("text=Cart (1 items)", timeout=10000)
            page.get_by_label("Cash received").fill("30000")
            page.get_by_role(
                "button", name=re.compile("Checkout")
            ).click()
            page.wait_for_selector("text=Sale complete", timeout=15000)
            page.get_by_role("button", name="New sale").click()
            print("PASS POS checkout completes with receipt modal")

            # --- Viewer role limits --------------------------------------
            page.get_by_role("button", name="Sign out").click()
            page.get_by_label("Username").fill("viewer")
            page.get_by_label("Password").fill("DemoPass!1234")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_selector("text=Key metrics", timeout=15000)

            nav_names = page.locator(".nav-item span").all_inner_texts()
            assert "Stock Movements" not in nav_names, nav_names
            assert "Users" not in nav_names, nav_names
            assert "POS" not in nav_names, nav_names
            print(
                "PASS viewer sees a reduced navigation (no pos/movements/users)"
            )

            page.get_by_role("button", name="Products").click()
            page.wait_for_selector("text=Product catalogue", timeout=10000)
            assert page.get_by_role("button", name="Add product").count() == 0
            print("PASS viewer cannot add products")

            browser.close()

    except Exception as exc:  # noqa: BLE001 - report and fail the run
        failures.append(str(exc))
        print("FAIL", exc)
    finally:
        for proc in (web, backend):
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    if failures:
        print(f"\n{len(failures)} browser E2E failure(s)")
        return 1

    print("\nALL BROWSER E2E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
