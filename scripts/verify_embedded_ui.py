"""Inspect the real local desktop inside the authorized Onshape test document."""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.ui_test_login import EMAIL, VAULT
from slicer_link.platforms import secret

DOCUMENT = (
    "https://cad.onshape.com/documents/1c8a32b93894e93c9d08d20b/"
    "w/4f589f82b3e96fa9380b6416/e/90ae2fc4f740e9253c9c2b7e"
)


def main():
    root = Path(__file__).resolve().parents[1] / "artifacts" / "embedded" / "browser"
    root.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        print("Launching isolated test browser.", flush=True)
        browser = p.chromium.launch_persistent_context(
            str(root / "profile"),
            channel="msedge",
            headless=True,
            viewport={"width": 1600, "height": 1200},
        )
        # Equivalent to accepting Onshape's local-network permission prompt,
        # scoped to this disposable test profile and this one origin.
        browser.grant_permissions(["local-network-access"], origin="https://cad.onshape.com")
        page = browser.pages[0]
        page.on(
            "console",
            lambda msg: (
                print("Browser: " + msg.text[:800], flush=True)
                if msg.type == "error" and ("localhost" in msg.text or "policy" in msg.text.lower())
                else None
            ),
        )
        page.on(
            "requestfailed",
            lambda req: (
                print("Local request failed: " + str(req.failure), flush=True)
                if req.url.startswith("http://localhost:8768/")
                else None
            ),
        )
        print("Opening test document.", flush=True)
        page.goto(DOCUMENT, wait_until="domcontentloaded")
        print("Document navigation completed.", flush=True)
        try:
            page.wait_for_function(
                "location.pathname.includes('/signin') || document.querySelector('iframe')", timeout=30000
            )
        except Exception:
            page.screenshot(path=str(root / "navigation-failure.png"))
            print(
                json.dumps(
                    {
                        "title": page.title(),
                        "path": page.evaluate("location.pathname"),
                        "text": page.locator("body").inner_text()[:1500],
                    }
                ),
                flush=True,
            )
            raise
        if "/signin" in page.url:
            print("Restoring authorized test-account login.", flush=True)
            page.locator("input[name=username]").fill(EMAIL)
            page.get_by_role("button", name="Continue", exact=True).click()
            page.locator("input[type=password]").wait_for(timeout=30000)
            assert page.url.startswith("https://cad.onshape.com/signin")
            assert page.locator("input[name=email]").input_value() == EMAIL
            password = secret(VAULT)
            assert password, "Test account password is not in the native credential store."
            page.locator("input[type=password]").fill(password)
            del password
            page.get_by_role("button", name="Sign in", exact=True).click()
        page.wait_for_url("**/documents/**", timeout=60000)
        print("Signed in; waiting for application tab.", flush=True)
        local = page.frame_locator('iframe[src^="http://localhost:8768/"]')
        try:
            local.locator("#choose").wait_for(timeout=30000)
        except Exception:
            page.screenshot(path=str(root / "embedding-failure.png"))
            print(
                json.dumps(
                    {
                        "title": page.title(),
                        "text": page.locator("body").inner_text()[:2000],
                        "frames": [frame.url.split("?")[0] for frame in page.frames],
                    }
                ),
                flush=True,
            )
            raise
        assert local.locator("#connection").inner_text() == "Onshape context received"
        if "--inspect-picker" in sys.argv or "--add-bambu" in sys.argv or "--add-orca" in sys.argv:
            kind = "orca" if "--add-orca" in sys.argv else "bambu"
            local.locator("#slicer").select_option(kind)
            local.locator("#open-desktop").click()
            local.frame_locator("#desktop").locator("canvas").first.wait_for()
            local.locator("#choose").click()
            page.wait_for_timeout(2000)
            page.get_by_text("The Second" if "--second" in sys.argv else "Prism", exact=True).first.click()
            page.wait_for_timeout(1000)
            page.get_by_text("Round" if "--second" in sys.argv else "Round test", exact=True).click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(root / "part-picker.png"))
            evidence = local.locator("body").evaluate("() => window.slicerLinkSelectionEvidence")
            print(json.dumps(evidence), flush=True)
            assert evidence and len(evidence) == 1
            if "--inspect-picker" not in sys.argv:
                local.locator("#add").click()
                local.locator("#add").wait_for(state="visible")
                for _ in range(120):
                    if local.locator("#choose").is_enabled():
                        break
                    page.wait_for_timeout(1000)
                status = local.locator("#desktop-status").inner_text()
                result = local.locator("body").evaluate("() => window.slicerLinkImportEvidence")
                page.screenshot(path=str(root / f"onshape-{kind}-import.png"))
                print(json.dumps({"status": status, "result": result}), flush=True)
                assert result and result["status"] == "verified"
            return
        for kind in ("orca", "bambu"):
            local.locator("#slicer").select_option(kind)
            local.locator("#open-desktop").click()
            desktop = local.frame_locator("#desktop")
            desktop.locator("canvas").first.wait_for(timeout=30000)
            page.wait_for_timeout(3000)
            local.locator("#desktop").scroll_into_view_if_needed()
            page.screenshot(path=str(root / f"onshape-{kind}.png"), full_page=True)
            print(
                json.dumps(
                    {
                        "slicer": kind,
                        "onshape_context": True,
                        "canvas_count": desktop.locator("canvas").count(),
                        "screenshot": str(root / f"onshape-{kind}.png"),
                    }
                ),
                flush=True,
            )
        browser.close()


if __name__ == "__main__":
    main()
