# scripts/save_app_state.py
from playwright.sync_api import sync_playwright
import sys

APP_BASE_URLS = {
    "Linear": "https://linear.app/",
    "Notion": "https://www.notion.so/",
    "Asana": "https://app.asana.com/",
}

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/save_app_state.py <AppName>")
        print("Example: python scripts/save_app_state.py Linear")
        sys.exit(1)

    app = sys.argv[1]
    if app not in APP_BASE_URLS:
        print(f"Unknown app {app!r}. Valid apps: {', '.join(APP_BASE_URLS)}")
        sys.exit(1)

    base_url = APP_BASE_URLS[app]
    state_filename = f"{app.lower()}_state.json"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(base_url)
        print(f"A browser window opened at {base_url}")
        print(f"Log in to {app} like you normally do.")
        print("Make sure you end up on your workspace/home UI.")
        input("When you're fully logged in, press Enter here... ")

        context.storage_state(path=state_filename)
        print(f"✅ Saved login state to {state_filename}")

        browser.close()

if __name__ == "__main__":
    main()
