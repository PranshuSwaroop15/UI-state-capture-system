# agent/executor.py

"""
Milestone B — Executor + State Capture (Skeleton)

This file defines the basic structure of the executor.
You can fill in the logic for each action yourself.
"""

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


# Optional: map app names to base URLs
APP_BASE_URLS = {
    "Linear": "https://linear.app/",
    "Notion": "https://www.notion.so/",
    "Asana": "https://app.asana.com/",
}


# -----------------------------
# Load steps from planner
# -----------------------------
def load_steps(run_dir: Path) -> List[Dict[str, Any]]:
    steps_path = run_dir / "steps.yaml"
    if not steps_path.exists():
        raise FileNotFoundError("steps.yaml not found in run folder.")
    return yaml.safe_load(steps_path.read_text())


# -----------------------------
# Perform each step (Dispatcher)
# -----------------------------
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

    elif action == "select":
        do_select(page, step, logger)

    elif action == "submit":
        do_submit(page, step, logger)

    elif action == "assert":
        do_assert(page, step, logger)

    else:
        logger.warning(f"Unknown action: {action}")


# -----------------------------
# Individual action handlers
# (fill these in yourself)
# -----------------------------


def dismiss_popups(page, logger):
    """
    Best-effort: close common popup patterns so the main UI is clickable.
    Safe if nothing is there.
    """
    # Common button labels on popups / tours
    labels = [
        "Got it",
        "Skip",
        "Maybe later",
        "Not now",
        "Close",
        "No thanks",
        "Dismiss",
    ]

    for label in labels:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            if btn.count() > 0:
                logger.info(f"[popups] Dismissing popup via button≈{label!r}")
                btn.first.click()
        except Exception:
            continue

    # Try generic close icons (aria-label)
    try:
        close_icon = page.locator('[aria-label="Close"], [aria-label="Dismiss"]')
        if close_icon.count() > 0:
            logger.info("[popups] Clicking close icon")
            close_icon.first.click()
    except Exception:
        pass

# def do_open(page, step, logger):
#     app = step.get("app")
#     base_url = APP_BASE_URLS.get(app)

#     if not base_url:
#         logger.warning(f"[open] Unknown app={app!r}, opening about:blank")
#         page.goto("about:blank")
#         return

#     logger.info(f"[open] Opening app={app} at {base_url}")
#     page.goto(base_url)
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

    # Try to clear any first-load popups
    # dismiss_popups(page, logger)


def do_goto(page, step, logger):
    section = step.get("section")
    if not section:
        logger.warning("[goto] Missing 'section' in step")
        return

    logger.info(f"[goto] Navigating to section={section!r}")

    # First try simple text match
    try:
        page.get_by_text(section, exact=False).first.click()
        return
    except Exception:
        logger.info("[goto] Direct text click failed, trying role-based locators")

    # Try links with that name
    try:
        locator = page.get_by_role("link", name=re.compile(section, re.I))
        if locator.count() > 0:
            locator.first.click()
            return
    except Exception:
        pass

    # Try buttons with that name
    try:
        locator = page.get_by_role("button", name=re.compile(section, re.I))
        if locator.count() > 0:
            locator.first.click()
            return
    except Exception:
        pass

    logger.warning(f"[goto] Could not find UI element for section={section!r}")


# def do_click(page, step, logger):
#     text = step.get("text")
#     if not text:
#         logger.warning("[click] Missing 'text' in step")
#         return

#     logger.info(f"[click] Clicking element with text≈{text!r}")
#     try:
#         page.get_by_text(text, exact=False).first.click()
#     except Exception as e:
#         logger.warning(f"[click] Failed to click element with text={text!r}: {e}")
# def do_click(page, step, logger):
#     text = step.get("text").lower().strip()

#     # -----------------------------------
#     # 1. Try plain match (normal case)
#     # -----------------------------------
#     btn = page.get_by_role("button", name=re.compile(text, re.I))
#     if btn.count() > 0:
#         logger.info(f"[click] Clicking element with text≈{text}")
#         btn.first.click()
#         return

#     # -----------------------------------
#     # 2. Smart fallback for synonyms
#     #    Without checking app name!
#     # -----------------------------------
#     fallbacks = {
#         "new project": ["Blank project", "Create project", "Add project", "New project","Create"],
#         "blank project": ["Blank project", "Start from scratch", "Create new"],
#         "create project": ["Blank project", "New project","Project"],
#     }

#     for key, candidates in fallbacks.items():
#         if key in text:
#             for label in candidates:
#                 fb = page.get_by_role("button", name=re.compile(label, re.I))
#                 if fb.count() > 0:
#                     logger.info(f"[click] Fallback matched≈{label}")
#                     fb.first.click()
#                     return

#     logger.warning(f"[click] No button matched text≈{text!r}")

# # working
def do_click(page, step, logger):
    raw_text = step.get("text")
    if not raw_text:
        logger.warning("[click] Missing 'text' in step")
        return

    text = raw_text.lower().strip()

    # 1) Try role=button, preferred
    try:
        btn = page.get_by_role("button", name=re.compile(text, re.I))
        if btn.count() > 0:
            logger.info(f"[click] Clicking button with text≈{raw_text!r}")
            btn.first.click()
            return
    except Exception:
        logger.info("[click] role=button match failed, trying synonyms")

    # 2) Smart fallback for synonyms (your existing mapping)
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

    # 3) Plain text-based fallback
    try:
        logger.info(f"[click] Fallback text search for≈{raw_text!r}")
        page.get_by_text(raw_text, exact=False).first.click()
        return
    except Exception as e:
        logger.warning(f"[click] No element matched text≈{raw_text!r}: {e}")
# def do_click(page, step, logger):
#     raw_text = step.get("text")
#     if not raw_text:
#         logger.warning("[click] Missing 'text' in step")
#         return

#     text = raw_text.strip()
#     logger.info(f"[click] Trying to click≈{text!r}")
#     pattern = re.compile(re.escape(text), re.I)

#     # 1) Try role=button (good for most “Create”, “New project”, etc.)
#     try:
#         btn = page.get_by_role("button", name=pattern)
#         count = btn.count()
#         logger.info(f"[click] role=button matches for {raw_text!r}: {count}")
#         if count > 0:
#             btn.first.click()
#             logger.info(f"[click] Clicked button≈{raw_text!r}")
#             return
#     except Exception as e:
#         logger.info(f"[click] role=button failed for {raw_text!r}: {e}")

#     # 2) Try role=link (for things that are links, not buttons)
#     try:
#         link = page.get_by_role("link", name=pattern)
#         count = link.count()
#         logger.info(f"[click] role=link matches for {raw_text!r}: {count}")
#         if count > 0:
#             link.first.click()
#             logger.info(f"[click] Clicked link≈{raw_text!r}")
#             return
#     except Exception as e:
#         logger.info(f"[click] role=link failed for {raw_text!r}: {e}")

#     # 3) Fallback: text search anywhere on the page
#     try:
#         loc = page.get_by_text(raw_text, exact=False)
#         count = loc.count()
#         logger.info(f"[click] text matches for {raw_text!r}: {count}")
#         if count > 0:
#             loc.first.click()
#             logger.info(f"[click] Clicked text≈{raw_text!r}")
#             return
#     except Exception as e:
#         logger.warning(f"[click] No element matched≈{raw_text!r}: {e}")

# def do_click(page, step, logger):
#     raw_text = step.get("text")
#     if not raw_text:
#         logger.warning("[click] Missing 'text' in step")
#         return

#     text = raw_text.strip()
#     lower = text.lower()

#     # 1) Prefer role=button (for "+ Create")
#     try:
#         btn = page.get_by_role("button", name=re.compile(text, re.I))
#         count = btn.count()
#         logger.info(f"[click] role=button matches for {raw_text!r}: {count}")
#         if count > 0:
#             logger.info(f"[click] Clicking button with text≈{raw_text!r}")
#             btn.first.click()
#             return
#     except Exception as e:
#         logger.info(f"[click] role=button match failed for {raw_text!r}: {e}. Trying menuitem")

#     # 2) Then try role=menuitem (for "Project" in the Create dropdown)
#     try:
#         menuitem = page.get_by_role("menuitem", name=re.compile(text, re.I))
#         count = menuitem.count()
#         logger.info(f"[click] role=menuitem matches for {raw_text!r}: {count}")
#         if count > 0:
#             logger.info(f"[click] Clicking menuitem with text≈{raw_text!r}")
#             menuitem.first.click()
#             return
#     except Exception as e:
#         logger.info(f"[click] role=menuitem match failed for {raw_text!r}: {e}. Trying link")

#     # 3) Links (generic)
#     try:
#         link = page.get_by_role("link", name=re.compile(text, re.I))
#         count = link.count()
#         logger.info(f"[click] role=link matches for {raw_text!r}: {count}")
#         if count > 0:
#             logger.info(f"[click] Clicking link with text≈{raw_text!r}")
#             link.first.click()
#             return
#     except Exception as e:
#         logger.info(f"[click] role=link match failed for {raw_text!r}: {e}. Trying synonyms/text")

#     # 4) Your existing synonyms (kept as-is if you still want them)
#     fallbacks = {
#         "new project": ["Blank project", "Create project", "Add project", "New project", "Create"],
#         "create project": ["Blank project", "New project", "Project"],
#     }
#     for key, candidates in fallbacks.items():
#         if key in lower:
#             for label in candidates:
#                 try:
#                     fb = page.get_by_role("button", name=re.compile(label, re.I))
#                     c2 = fb.count()
#                     logger.info(f"[click] fallback role=button matches for {label!r}: {c2}")
#                     if c2 > 0:
#                         logger.info(f"[click] Fallback matched≈{label!r}")
#                         fb.first.click()
#                         return
#                 except Exception:
#                     continue

#     # 5) Fallback to exact text match (avoid matching "Projects" when we want "Project")
#     try:
#         logger.info(f"[click] Fallback exact text search for≈{raw_text!r}")
#         loc = page.get_by_text(raw_text, exact=True)
#         count = loc.count()
#         logger.info(f"[click] exact text matches for {raw_text!r}: {count}")
#         if count > 0:
#             loc.first.click()
#             return
#     except Exception as e:
#         logger.warning(f"[click] No element matched text≈{raw_text!r}: {e}")
# def do_click(page, step, logger):
#     raw_text = step.get("text")
#     if not raw_text:
#         logger.warning("[click] Missing 'text' in step")
#         return

#     text = raw_text.strip()
#     logger.info(f"[click] Trying to click≈{text!r}")

#     # 1) Buttons (good for "Create")
#     try:
#         btn = page.get_by_role("button", name=re.compile(text, re.I))
#         count = btn.count()
#         logger.info(f"[click] role=button matches for {raw_text!r}: {count}")
#         if count > 0:
#             btn.first.click()
#             logger.info(f"[click] Clicked button≈{raw_text!r}")
#             return
#     except Exception as e:
#         logger.info(f"[click] role=button failed for {raw_text!r}: {e}")

#     # 2) Menu items (good for "Project" in the Create dropdown)
#     try:
#         mi = page.get_by_role("menuitem", name=re.compile(text, re.I))
#         count = mi.count()
#         logger.info(f"[click] role=menuitem matches for {raw_text!r}: {count}")
#         if count > 0:
#             mi.first.click()
#             logger.info(f"[click] Clicked menuitem≈{raw_text!r}")
#             return
#     except Exception as e:
#         logger.info(f"[click] role=menuitem failed for {raw_text!r}: {e}")

#     # 3) Links
#     try:
#         link = page.get_by_role("link", name=re.compile(text, re.I))
#         count = link.count()
#         logger.info(f"[click] role=link matches for {raw_text!r}: {count}")
#         if count > 0:
#             link.first.click()
#             logger.info(f"[click] Clicked link≈{raw_text!r}")
#             return
#     except Exception as e:
#         logger.info(f"[click] role=link failed for {raw_text!r}: {e}")

#     # 4) Exact text (avoid hitting "Projects" when we want "Project")
#     try:
#         loc = page.get_by_text(raw_text, exact=True)
#         count = loc.count()
#         logger.info(f"[click] exact-text matches for {raw_text!r}: {count}")
#         if count > 0:
#             loc.first.click()
#             logger.info(f"[click] Clicked exact-text≈{raw_text!r}")
#             return
#     except Exception as e:
#         logger.warning(f"[click] No element matched≈{raw_text!r}: {e}")

# def do_fill(page, step, logger):
#     field = step.get("field")
#     val = step.get("val", "")
#     if not field:
#         logger.warning("[fill] Missing 'field' in step")
#         return

#     logger.info(f"[fill] Filling field≈{field!r} with value={val!r}")

#     # Strategy 1: label-based
#     try:
#         page.get_by_label(field, exact=False).fill(str(val))
#         return
#     except Exception:
#         logger.info("[fill] Label-based fill failed, trying placeholder")

#     # Strategy 2: placeholder-based
#     try:
#         page.get_by_placeholder(field).fill(str(val))
#         return
#     except Exception:
#         logger.info("[fill] Placeholder-based fill failed, trying generic input")

#     # Strategy 3: generic input fallback
#     try:
#         page.locator("input[type='text']").first.fill(str(val))
#         return
#     except Exception as e:
#         logger.warning(f"[fill] Failed to fill any input for field={field!r}: {e}")
# def do_fill(page, step, logger):
#     field = step.get("field")
#     val = step.get("val", "")
#     if not field:
#         logger.warning("[fill] Missing 'field' in step")
#         return

#     text_val = str(val)
#     logger.info(f"[fill] Filling field≈{field!r} with value={text_val!r}")

#     # 1) Label-based
#     try:
#         locator = page.get_by_label(field, exact=False)
#         if locator.count() > 0:
#             logger.info("[fill] Using label-based locator")
#             locator.first.fill(text_val)
#             return
#     except Exception:
#         logger.info("[fill] Label-based fill failed, trying placeholder")

#     # 2) Placeholder-based
#     try:
#         locator = page.get_by_placeholder(field)
#         if locator.count() > 0:
#             logger.info("[fill] Using placeholder-based locator")
#             locator.first.fill(text_val)
#             return
#     except Exception:
#         logger.info("[fill] Placeholder-based fill failed, trying aria-label/name")

#     # 3) aria-label / name attributes
#     try:
#         css = (
#             f"input[aria-label*='{field}'], textarea[aria-label*='{field}'], "
#             f"input[name*='{field}'], textarea[name*='{field}']"
#         )
#         locator = page.locator(css)
#         if locator.count() > 0:
#             logger.info("[fill] Using aria-label/name-based locator")
#             locator.first.fill(text_val)
#             return
#     except Exception:
#         logger.info("[fill] aria-label/name-based fill failed, trying role=textbox")

#     # 4) Generic textbox role
#     try:
#         locator = page.get_by_role("textbox")
#         if locator.count() > 0:
#             logger.info("[fill] Using first role=textbox as fallback")
#             locator.first.fill(text_val)
#             return
#     except Exception as e:
#         logger.info(f"[fill] role=textbox fill failed: {e}. Trying text-click fallback")

#     # 5) Last resort: click text≈field and type
#     #    (works for Notion "Untitled" title and other contenteditable UIs)
#     try:
#         logger.info(f"[fill] Trying text-click typing for field={field!r}")
#         title = page.get_by_text(field, exact=False).first
#         title.click()
#         page.keyboard.type(text_val)
#         return
#     except Exception as e:
#         logger.warning(f"[fill] Failed to fill any field for {field!r}: {e}")

#working
def do_fill(page, step, logger):
    field = step.get("field")
    val = step.get("val", "")
    if not field:
        logger.warning("[fill] Missing 'field' in step")
        return

    text_val = str(val)
    logger.info(f"[fill] Filling field≈{field!r} with value={text_val!r}")

    # 1) Label-based
    try:
        locator = page.get_by_label(field, exact=False)
        if locator.count() > 0:
            logger.info("[fill] Using label-based locator")
            locator.first.fill(text_val)
            return
    except Exception:
        logger.info("[fill] Label-based fill failed, trying placeholder")

    # 2) Placeholder-based (exact match)
    try:
        locator = page.get_by_placeholder(field)
        if locator.count() > 0:
            logger.info("[fill] Using placeholder-based locator")
            locator.first.fill(text_val)
            return
    except Exception:
        logger.info("[fill] Placeholder-based fill failed, trying aria-label/name")

    # 3) aria-label / name attributes (substring match)
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

    # 4) Generic textbox role
    try:
        locator = page.get_by_role("textbox")
        if locator.count() > 0:
            logger.info("[fill] Using first role=textbox as fallback")
            locator.first.fill(text_val)
            return
    except Exception as e:
        logger.info(f"[fill] role=textbox fill failed: {e}. Trying generic input/textarea")

    # 5) Generic input/textarea
    try:
        locator = page.locator("input, textarea")
        if locator.count() > 0:
            logger.info("[fill] Using first <input>/<textarea> as fallback")
            locator.first.fill(text_val)
            return
    except Exception as e:
        logger.info(f"[fill] generic input/textarea fill failed: {e}. Trying text-click fallback")

    # 6) Last resort: click text≈field and type (for contenteditable)
    try:
        logger.info(f"[fill] Trying text-click typing for field={field!r}")
        title = page.get_by_text(field, exact=False).first
        title.click()
        page.keyboard.type(text_val)
        return
    except Exception as e:
        logger.warning(f"[fill] Failed to fill any field for {field!r}: {e}")

# def do_fill(page, step, logger):
#     field = step.get("field")
#     val = step.get("val", "")
#     if not field:
#         logger.warning("[fill] Missing 'field' in step")
#         return

#     text_val = str(val)
#     logger.info(f"[fill] Filling field≈{field!r} with value={text_val!r}")

#     # 0) Exact placeholder match (nice for Asana "Project name")
#     try:
#         placeholder_locator = page.locator(
#             f"input[placeholder='{field}'], textarea[placeholder='{field}']"
#         )
#         if placeholder_locator.count() > 0:
#             logger.info("[fill] Using exact placeholder match")
#             placeholder_locator.first.fill(text_val)
#             return
#     except Exception:
#         logger.info("[fill] Exact placeholder match failed, trying label")

#     # 1) Label-based
#     try:
#         locator = page.get_by_label(field, exact=False)
#         if locator.count() > 0:
#             logger.info("[fill] Using label-based locator")
#             locator.first.fill(text_val)
#             return
#     except Exception:
#         logger.info("[fill] Label-based fill failed, trying placeholder helper")

#     # 2) Placeholder-based (Playwright helper)
#     try:
#         locator = page.get_by_placeholder(field)
#         if locator.count() > 0:
#             logger.info("[fill] Using placeholder-based locator")
#             locator.first.fill(text_val)
#             return
#     except Exception:
#         logger.info("[fill] Placeholder-based fill failed, trying aria-label/name")

#     # 3) aria-label / name attributes
#     try:
#         css = (
#             f"input[aria-label*='{field}'], textarea[aria-label*='{field}'], "
#             f"input[name*='{field}'], textarea[name*='{field}']"
#         )
#         locator = page.locator(css)
#         if locator.count() > 0:
#             logger.info("[fill] Using aria-label/name-based locator")
#             locator.first.fill(text_val)
#             return
#     except Exception:
#         logger.info("[fill] aria-label/name-based fill failed, trying role=textbox")

#     # 4) Generic textbox role
#     try:
#         locator = page.get_by_role("textbox")
#         if locator.count() > 0:
#             logger.info("[fill] Using first role=textbox as fallback")
#             locator.first.fill(text_val)
#             return
#     except Exception as e:
#         logger.info(f"[fill] role=textbox fill failed: {e}. Trying generic input/textarea")

#     # 5) Generic input/textarea (very generic)
#     try:
#         locator = page.locator("input[type='text'], textarea")
#         if locator.count() > 0:
#             logger.info("[fill] Using first text <input>/<textarea> as fallback")
#             locator.first.fill(text_val)
#             return
#     except Exception as e:
#         logger.info(f"[fill] generic input/textarea fill failed: {e}. Trying text-click fallback")

#     # 6) Last resort: click some text≈field and type (for contenteditable, Notion titles, etc.)
#     try:
#         logger.info(f"[fill] Trying text-click typing for field={field!r}")
#         title = page.get_by_text(field, exact=False).first
#         title.click()
#         page.keyboard.type(text_val)
#         return
#     except Exception as e:
#         logger.warning(f"[fill] Failed to fill any field for {field!r}: {e}")

# def do_select(page, step, logger):
#     field = step.get("field")
#     opt = step.get("opt")

#     if not field or not opt:
#         logger.warning("[select] Missing 'field' or 'opt' in step")
#         return

#     logger.info(f"[select] Selecting option={opt!r} in field≈{field!r}")

#     # 1) Label-based <select>
#     try:
#         select_el = page.get_by_label(field, exact=False)
#         if select_el.count() > 0:
#             logger.info("[select] Using label-based <select>")
#             select_el.first.select_option(label=opt)
#             return
#     except Exception:
#         logger.info("[select] Label-based select failed, trying placeholder")

#     # 2) Placeholder-based
#     try:
#         select_el = page.get_by_placeholder(field)
#         if select_el.count() > 0:
#             logger.info("[select] Using placeholder-based <select>")
#             select_el.first.select_option(label=opt)
#             return
#     except Exception:
#         logger.info("[select] Placeholder-based select failed, trying generic <select>")

#     # 3) Generic <select> fallback
#     try:
#         select_el = page.locator("select")
#         if select_el.count() > 0:
#             logger.info("[select] Using first <select> element as fallback")
#             select_el.first.select_option(label=opt)
#             return
#     except Exception as e:
#         logger.warning(f"[select] Failed to select option={opt!r} for field={field!r}: {e}")

def do_submit(page, step, logger):
    logger.info("[submit] Trying to submit (generic heuristic)")

    # Try a bunch of common button labels that mean "confirm"
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


# -----------------------------
# Main entrypoint
# -----------------------------
# def execute_plan(run_dir: Path, logger) -> None:
#     """
#     - Reads steps.yaml
#     - Opens a browser
#     - Executes steps in order
#     - Takes screenshots after each step
#     """

#     steps = load_steps(run_dir)
#     states_dir = run_dir / "states"
#     states_dir.mkdir(exist_ok=True)

#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         page = browser.new_page()

#         for i, step in enumerate(steps, start=1):
#             perform_step(page, step, logger)

#             # Screenshot after each step
#             screenshot_path = states_dir / f"{i:02d}_{step['action']}.png"
#             page.screenshot(path=str(screenshot_path))

#         browser.close()

def capture_state(page, step, idx: int, states_dir: Path):
    """Capture screenshot + metadata for this step."""
    screenshot_name = f"{idx:02d}_{step.get('action', 'unknown')}.png"
    screenshot_path = states_dir / screenshot_name

    # Screenshot
    page.screenshot(path=str(screenshot_path), full_page=True)

    # Basic metadata
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

    # figure out which app this run is for (first `open` step with app)
    app = None
    for s in steps:
        if s.get("action") == "open" and s.get("app"):
            app = s["app"]
            break
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        # choose storage_state file if available
        state_file = APP_STATE_FILES.get(app)
        if state_file and Path(state_file).exists():
            logger.info(f"[execute_plan] Using storage_state={state_file!r} for app={app!r}")
            context = browser.new_context(storage_state=state_file)
        else:
            logger.info(f"[execute_plan] No storage_state for app={app!r}; using empty context")
            context = browser.new_context()

        page = context.new_page()

        # for i, step in enumerate(steps, start=1):
        #     perform_step(page, step, logger)

        #     screenshot_path = states_dir / f"{i:02d}_{step['action']}.png"
        #     page.screenshot(path=str(screenshot_path))
        for i, step in enumerate(steps, start=1):
            try:
                logger.info(f"[step {i}] {step}")
                perform_step(page, step, logger)
            except Exception as e:
                logger.warning(f"[step {i}] Error executing step {step}: {e}")
            state = capture_state(page, step, i, states_dir)
            states.append(state)
            # screenshot_path = states_dir / f"{i:02d}_{step['action']}.png"
            # page.screenshot(path=str(screenshot_path))

        browser.close()
        
    (run_dir / "states.json").write_text(
        json.dumps(states, indent=2),
        encoding="utf-8",
    )