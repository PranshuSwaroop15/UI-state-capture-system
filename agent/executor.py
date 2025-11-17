from pathlib import Path
from typing import Dict, List, Any
import yaml
import re
import json
import hashlib
from playwright.sync_api import sync_playwright

APP_STATE_FILES = {
    "Linear": "linear_state.json",
    "Notion": "notion_state.json",
    "Asana": "asana_state.json",
}



APP_BASE_URLS = {
    "Linear": "https://linear.app/",
    "Notion": "https://www.notion.so/",
    "Asana": "https://app.asana.com/",
}


def load_steps(run_dir: Path) -> List[Dict[str, Any]]:
    steps_path = run_dir / "steps.yaml"
    if not steps_path.exists():
        raise FileNotFoundError("steps.yaml not found in run folder.")
    return yaml.safe_load(steps_path.read_text())



def perform_step(page, step: Dict[str, Any], logger):
    action = step.get("action")

    if action == "open":
        do_open(page, step, logger)

    elif action == "goto":
        do_goto(page, step, logger)

    elif action == "click":
        do_click(page, step, logger)

    elif action == "fill":
        do_fill(page, step, logger)
    
    elif action == "submit":
        do_submit(page, step, logger)

    elif action == "assert":
        do_assert(page, step, logger)

    else:
        logger.warning(f"Unknown action: {action}")



def do_open(page, step, logger):
    app = step.get("app")
    base_url = APP_BASE_URLS.get(app)

    if not base_url:
        logger.warning(f"[open] Unknown app={app!r}, opening about:blank")
        page.goto("about:blank")
        return

    logger.info(f"[open] Opening app={app} at {base_url}")
    page.goto(base_url)
    page.wait_for_load_state("networkidle")




def do_goto(page, step, logger):
    section = step.get("section")
    if not section:
        logger.warning("[goto] Missing 'section' in step")
        return

    logger.info(f"[goto] Navigating to section={section!r}")

   
    try:
        page.get_by_text(section, exact=False).first.click()
        return
    except Exception:
        logger.info("[goto] Direct text click failed, trying role-based locators")

  
    try:
        locator = page.get_by_role("link", name=re.compile(section, re.I))
        if locator.count() > 0:
            locator.first.click()
            return
    except Exception:
        pass

   
    try:
        locator = page.get_by_role("button", name=re.compile(section, re.I))
        if locator.count() > 0:
            locator.first.click()
            return
    except Exception:
        pass

    logger.warning(f"[goto] Could not find UI element for section={section!r}")



def do_click(page, step, logger):
    raw_text = step.get("text")
    if not raw_text:
        logger.warning("[click] Missing 'text' in step")
        return

    text = raw_text.lower().strip()

    if "new page" in text:
        try:
            locator = page.locator(
               
                "[aria-label*='new page' i], "
                "[data-testid*='new-page' i], "
                "button[aria-label*='new' i]"
            )
            count = locator.count()
            logger.info(f"[click] 'New page' heuristic matches: {count}")
            if count > 0:
                locator.first.click()
                logger.info("[click] Clicked using 'New page' heuristic")
                return
        except Exception as e:
            logger.info(f"[click] 'New page' heuristic failed: {e}")
   
    try:
        btn = page.get_by_role("button", name=re.compile(text, re.I))
        if btn.count() > 0:
            logger.info(f"[click] Clicking button with text≈{raw_text!r}")
            btn.first.click()
            return
    except Exception:
        logger.info("[click] role=button match failed, trying synonyms")

   
    fallbacks = {
        "new project": ["Blank project", "Create project", "Add project", "New project", "Create"],
        "create project": ["Blank project", "New project", "Project"],
    }

    for key, candidates in fallbacks.items():
        if key in text:
            for label in candidates:
                try:
                    fb = page.get_by_role("button", name=re.compile(label, re.I))
                    if fb.count() > 0:
                        logger.info(f"[click] Fallback matched≈{label!r}")
                        fb.first.click()
                        return
                except Exception:
                    continue

   
    try:
        logger.info(f"[click] Fallback text search for≈{raw_text!r}")
        page.get_by_text(raw_text, exact=False).first.click()
        return
    except Exception as e:
        logger.warning(f"[click] No element matched text≈{raw_text!r}: {e}")


def do_fill(page, step, logger):
    field = step.get("field")
    val = step.get("val", "")
    if not field:
        logger.warning("[fill] Missing 'field' in step")
        return

    text_val = str(val)
    logger.info(f"[fill] Filling field≈{field!r} with value={text_val!r}")
    
    if field.lower() in {"new page", "untitled", "title", "new database"}:
        try:
            loc = page.locator(
                '[placeholder="New page"], [placeholder="Untitled"], '
                '[placeholder="New database"], '
                '[data-placeholder="New page"], [data-placeholder="Untitled"], [data-placeholder="New database"]'
            )
            count = loc.count()
            logger.info(f"[fill] Notion-title matches for {field!r}: {count}")
            if count > 0:
                el = loc.first
                el.click()
                page.keyboard.press("Meta+A")  
                page.keyboard.press("Backspace")
                page.keyboard.type(text_val)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1000)
                logger.info("[fill] Filled Notion title/database name and committed")
                return
        except Exception as e:
            logger.info(f"[fill] Notion title special-case failed: {e}")
    # 1) Label-based
    try:
        locator = page.get_by_label(field, exact=False)
        if locator.count() > 0:
            logger.info("[fill] Using label-based locator")
            locator.first.fill(text_val)
            return
    except Exception:
        logger.info("[fill] Label-based fill failed, trying placeholder")


    try:
        locator = page.get_by_placeholder(field)
        if locator.count() > 0:
            logger.info("[fill] Using placeholder-based locator")
            locator.first.fill(text_val)
            return
    except Exception:
        logger.info("[fill] Placeholder-based fill failed, trying aria-label/name")

   
    try:
        css = (
            f"input[aria-label*='{field}'], textarea[aria-label*='{field}'], "
            f"input[name*='{field}'], textarea[name*='{field}']"
        )
        locator = page.locator(css)
        if locator.count() > 0:
            logger.info("[fill] Using aria-label/name-based locator")
            locator.first.fill(text_val)
            return
    except Exception:
        logger.info("[fill] aria-label/name-based fill failed, trying role=textbox")

  
    try:
        locator = page.get_by_role("textbox")
        if locator.count() > 0:
            logger.info("[fill] Using first role=textbox as fallback")
            locator.first.fill(text_val)
            return
    except Exception as e:
        logger.info(f"[fill] role=textbox fill failed: {e}. Trying generic input/textarea")

 
    try:
        locator = page.locator("input, textarea")
        if locator.count() > 0:
            logger.info("[fill] Using first <input>/<textarea> as fallback")
            locator.first.fill(text_val)
            return
    except Exception as e:
        logger.info(f"[fill] generic input/textarea fill failed: {e}. Trying text-click fallback")

   
    try:
        logger.info(f"[fill] Trying text-click typing for field={field!r}")
        title = page.get_by_text(field, exact=False).first
        title.click()
        page.keyboard.type(text_val)
        return
    except Exception as e:
        logger.warning(f"[fill] Failed to fill any field for {field!r}: {e}")


def do_submit(page, step, logger):
    logger.info("[submit] Trying to submit (generic heuristic)")

    
    common_labels = [
        "Create project",
        "Create",
        "Save",
        "Submit",
        "Done",
        "OK",
        "Continue",
        "Add",
    ]

    for label in common_labels:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            count = btn.count()
            logger.info(f"[submit] role=button matches for {label!r}: {count}")
            if count > 0:
                btn.first.click()
                logger.info(f"[submit] Clicked button with label≈{label!r}")
                return
        except Exception:
            continue

    logger.warning("[submit] No submit-like button found; nothing clicked.")


def do_assert(page, step, logger):
    token = step.get("token")
    if not token:
        logger.warning("[assert] Missing 'token' in step")
        return

    logger.info(f"[assert] Checking if token={token!r} appears in page text")
    try:
        body_text = page.text_content("body") or ""
    except Exception as e:
        logger.warning(f"[assert] Failed to read page text: {e}")
        return

    if token.lower() in body_text.lower():
        logger.info(f"[assert] PASSED: found token={token!r}")
    else:
        logger.warning(f"[assert] FAILED: token={token!r} not found")


def capture_state(page, step, idx: int, states_dir: Path):
    screenshot_name = f"{idx:02d}_{step.get('action', 'unknown')}.png"
    screenshot_path = states_dir / screenshot_name

    page.screenshot(path=str(screenshot_path), full_page=True)

    try:
        url = page.url
    except Exception:
        url = None

    try:
        body_html = page.inner_html("body")
        dom_hash = hashlib.sha256(body_html.encode("utf-8")).hexdigest()
    except Exception:
        dom_hash = None

    return {
        "index": idx,
        "action": step.get("action"),
        "state_label": step.get("state_label"),   # <- from planner
        "step": step,
        "url": url,
        "screenshot": screenshot_name,
        "dom_hash": dom_hash,
    }

def execute_plan(run_dir: Path, logger) -> None:
    """
    - Reads steps.yaml
    - Opens a browser
    - Executes steps in order
    - Takes screenshots after each step
    """

    steps = load_steps(run_dir)
    states_dir = run_dir / "states"
    states_dir.mkdir(exist_ok=True)

    states = []

   
    app = None
    for s in steps:
        if s.get("action") == "open" and s.get("app"):
            app = s["app"]
            break
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)


        state_file = APP_STATE_FILES.get(app)
        if state_file and Path(state_file).exists():
            logger.info(f"[execute_plan] Using storage_state={state_file!r} for app={app!r}")
            context = browser.new_context(storage_state=state_file)
        else:
            logger.info(f"[execute_plan] No storage_state for app={app!r}; using empty context")
            context = browser.new_context()

        page = context.new_page()

        for i, step in enumerate(steps, start=1):
            try:
                logger.info(f"[step {i}] {step}")
                perform_step(page, step, logger)
            except Exception as e:
                logger.warning(f"[step {i}] Error executing step {step}: {e}")
            state = capture_state(page, step, i, states_dir)
            states.append(state)
           
        logger.info("[execute_plan] Run finished; waiting 2s for autosave")
        page.wait_for_timeout(2000)

        browser.close()
        
    (run_dir / "states.json").write_text(
        json.dumps(states, indent=2),
        encoding="utf-8",
    )