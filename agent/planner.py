# agent/planner
from pathlib import Path
import yaml
import re
from typing import Dict, List, Any, Optional
import string
from difflib import get_close_matches


CONFIG_DIR = Path(__file__).parent / "config"


# ---------------------------
# LOAD CONFIGS
# ---------------------------
def _load_configs():
    with open(CONFIG_DIR / "intents.yaml") as f:
        intents_cfg = yaml.safe_load(f)

    with open(CONFIG_DIR / "app_names.yaml") as f:
        app_names = yaml.safe_load(f)["apps"]

    return intents_cfg, app_names


# ---------------------------
# NORMALIZATION
# ---------------------------
def _normalize(prompt: str) -> str:
    prompt = prompt.lower()
    prompt = prompt.translate(str.maketrans("", "", string.punctuation))
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt


# ---------------------------
# APP DETECTION
# ---------------------------
def _detect_app(prompt: str, apps: List[str]) -> Optional[str]:
    tokens = re.findall(r"[a-zA-Z]+", prompt.lower())
    apps_lower = [a.lower() for a in apps]

    for token in tokens:
        match = get_close_matches(token, apps_lower, n=1, cutoff=0.7)
        if match:
            idx = apps_lower.index(match[0])
            return apps[idx]

    return None


# ---------------------------
# INTENT + OBJECT DETECTION
# ---------------------------
def _detect_intent_object(prompt: str, intents_cfg):
    tokens = re.findall(r"[a-zA-Z]+", prompt.lower())

    # Build vocab: word → intent
    intent_vocab: Dict[str, str] = {}
    for intent_name, info in intents_cfg.get("intents", {}).items():
        for v in info.get("verbs", []):
            intent_vocab[v.lower()] = intent_name

    # Build vocab: word → object
    object_vocab: Dict[str, str] = {}
    for obj_name, info in intents_cfg.get("objects", {}).items():
        for n in info.get("nouns", []):
            object_vocab[n.lower()] = obj_name

    intent = None
    obj = None

    intent_words = list(intent_vocab.keys())
    object_words = list(object_vocab.keys())

    for token in tokens:
        if intent is None:
            match = get_close_matches(token, intent_words, n=1, cutoff=0.7)
            if match:
                intent = intent_vocab[match[0]]

        if obj is None:
            match = get_close_matches(token, object_words, n=1, cutoff=0.7)
            if match:
                obj = object_vocab[match[0]]

    return intent, obj


# ---------------------------
# BUILD STEPS
# ---------------------------
def _build_steps(intent: str | None,
                 obj: str | None,
                 app: str | None,
                 prompt: str) -> List[Dict[str, Any]]:

    if app is None:
        app = "<UNKNOWN_APP>"

    if obj is None:
        obj = "item"

    name = extract_possible_name(prompt, obj, app)

    if intent == "create":
        return _steps_create(obj, app, name)

    if intent == "filter":
        criteria = extract_filter_value(prompt)
        return _steps_filter(obj, app, criteria)

    if intent == "update":
        return _steps_update(obj, app, name)

    if intent == "delete":
        return _steps_delete(obj, app, name)

    if intent == "open":
        return _steps_open(obj, app)

    # fallback
    return [
        {"action": "open", "app": app},
        {"action": "assert", "token": "opened"},
    ]


# ---------------------------
# WRITE STEPS
# ---------------------------
def _write_steps_yaml(steps, run_dir: Path):
    with open(run_dir / "steps.yaml", "w") as f:
        yaml.safe_dump(steps, f, sort_keys=False)


# ---------------------------
# MAIN ENTRYPOINT
# ---------------------------
def plan(prompt: str, run_dir: Path, logger) -> None:
    intents_cfg, app_names = _load_configs()
    norm = _normalize(prompt)

    app = _detect_app(norm, app_names)
    intent, obj = _detect_intent_object(norm, intents_cfg)

    logger.info(f"Parsed: intent={intent}, object={obj}, app={app}")

    steps = _build_steps(intent, obj, app, prompt)
    _write_steps_yaml(steps, run_dir)

    logger.info(f"Planner wrote {len(steps)} steps → {run_dir/'steps.yaml'}")


# ---------------------------
# STEP TEMPLATES
# ---------------------------
# def _steps_create(obj: str, app: str, name: str):
#     return [
#         {"action": "open", "app": app},
#         {"action": "goto", "section": f"{obj}s"},
#         {"action": "click", "text": f"new {obj}"},
#         {"action": "fill", "field": "name", "val": name or "<AUTO_NAME>"},
#         {"action": "create project"},
#         {"action": "assert", "token": "created"},
#     ]
# def _steps_create(obj, app, name):
#     steps = [
#         {"action": "open", "app": app},
#         {"action": "goto", "section": f"{obj}s"},
#         {"action": "click", "text": f"new {obj}"},
#     ]

#     # Additional modal step for apps like Linear / Asana
#     if app in ["Linear", "Asana"]:
#         steps.append({"action": "click", "text": "Blank project"})

#     steps.extend([
#         {"action": "fill", "field": "name", "val": name or "<AUTO_NAME>"},
#         {"action": "submit"},
#         {"action": "assert", "token": "created"},
#     ])
#     return steps

# def _steps_create(obj: str | None, app: str | None, name: str | None):
#     title = name or "<AUTO_NAME>"

#     # 🔹 1) Notion: create page
#     if app == "Notion" and obj == "page":
#         # Flow:
#         # 1) open notion
#         # 2) click "New page" in sidebar
#         # 3) type title into "Untitled"
#         # 4) assert the title appears
#         return [
#             {"action": "open", "app": app},
#             {"action": "click", "text": "New page"},
#             {"action": "fill", "field": "Untitled", "val": title},
#             {"action": "assert", "token": title},
#         ]

#     # 🔹 2) Linear: create project
#     if app == "Linear" and obj == "project":
#         section = "Projects"
#         click_text = "New project"
#         field = "Name"           # closer to real UI
#         assert_token = "Project" # something that likely appears on success

#     # 🔹 3) Asana: create project
#     # elif app == "Asana" and obj == "project":
#     #     section = "Projects"
#     #     click_text = "New project"
#     #     field = "Project name"   # real label / placeholder
#     #     assert_token = "Project"
#     elif app == "Asana" and obj == "project":
#         title = name or "<AUTO_NAME>"
#         return [
#             {"action": "open", "app": app},
#             {"action": "goto", "section": "Projects"},
#             {"action": "click", "text": "New project"},
#             # Let whatever Asana shows be the default mode/template.
#             # Just try to fill the main project name field and submit.
#             {"action": "fill", "field": "Project name", "val": title},
#             {"action": "submit"},
#             {"action": "assert", "token": title},
#         ]

#     # 🔹 4) Generic create fallback
#     else:
#         section = f"{obj}s" if obj else None
#         click_text = f"new {obj}" if obj else "new"
#         field = "name"
#         assert_token = "created"

#     steps: List[Dict[str, Any]] = [
#         {"action": "open", "app": app},
#     ]

#     if section:
#         steps.append({"action": "goto", "section": section})

#     steps.extend(
#         [
#             {"action": "click", "text": click_text},
#             {"action": "fill", "field": field, "val": title},
#             {"action": "submit"},
#             {"action": "assert", "token": assert_token},
#         ]
#     )

#     return steps

#Working
def _steps_create(obj: str | None, app: str | None, name: str | None):
    title = name or "<AUTO_NAME>"

    # 🔹 Notion page (if you have this branch, keep it)
    if app == "Notion" and obj == "page":
        return [
            {"action": "open", "app": app},
            {"action": "click", "text": "New page"},
            {"action": "fill", "field": "Untitled", "val": title},
            {"action": "assert", "token": title},
        ]

    # 🔹 Asana: use top-left "Create" menu, not sidebar "Projects"
    if app == "Asana" and obj == "project":
         return [
            # {"action": "open", "app": app},
            # {"action": "click", "text": "Create"},          # top-left red button
            # {"action": "click", "text": "Project"},
            # {"action": "fill", "field": "Project name", "val": title},
            # {"action": "submit"},
            # {"action": "assert", "token": title},
            {"action": "open", "app": app, "state_label": "linear_home"},
            {"action": "goto", "section": "Projects", "state_label": "projects_list"},
            {"action": "click", "text": "New project", "state_label": "create_project_modal_open"},
            {"action": "fill", "field": "Name", "val": title, "state_label": "project_form_filled"},
            {"action": "submit", "state_label": "project_submit_clicked"},
            {"action": "assert", "token": "Project", "state_label": "project_created"},
        ]

    #🔹 Linear: create project (your existing working flow)
    if app == "Linear" and obj == "project":
        section = "Projects"
        click_text = "New project"
        field = "Name"
        assert_token = "Project"

        return [
            # {"action": "open", "app": app},
            # {"action": "goto", "section": section},
            # {"action": "click", "text": click_text},
            # {"action": "fill", "field": field, "val": title},
            # {"action": "submit"},
            # {"action": "assert", "token": assert_token},
        
          
        {"action": "open", "app": app, "state_label": "linear_home"},
        {"action": "goto", "section": "Projects", "state_label": "projects_list"},
        {"action": "click", "text": "New project", "state_label": "create_project_modal_open"},
        {"action": "fill", "field": "Name", "val": title, "state_label": "project_form_filled"},
        {"action": "submit", "state_label": "project_submit_clicked"},
        {"action": "assert", "token": "Project", "state_label": "project_created"},

        ]
    
    if app == "Linear" and obj == "issue":
        return [
            {"action": "open", "app": app, "state_label": "linear_home"},
            {"action": "goto", "section": "Issues", "state_label": "issues_list"},
            {"action": "click", "text": "New issue", "state_label": "new_issue_modal_open"},
            {"action": "fill", "field": "Title", "val": title, "state_label": "issue_title_filled"},

            # 🔥 THIS IS THE FIX:
            {"action": "click", "text": "Create issue", "state_label": "issue_created_button_clicked"},

            {"action": "assert", "token": title, "state_label": "issue_created"},
        ]


    # 🔹 Generic fallback
    section = f"{obj}s" if obj else None
    click_text = f"new {obj}" if obj else "new"
    field = "name"
    assert_token = "created"

    steps: List[Dict[str, Any]] = [{"action": "open", "app": app}]
    if section:
        steps.append({"action": "goto", "section": section})

    steps.extend(
        [
            {"action": "click", "text": click_text},
            {"action": "fill", "field": field, "val": title},
            {"action": "submit"},
            {"action": "assert", "token": assert_token},
        ]
    )
    
    return steps

# def _steps_create(obj: str | None, app: str | None, name: str | None):
#     title = name or "<AUTO_NAME>"

#     # --- Asana: use top-left Create menu only ---
#     if app == "Asana" and obj == "project":
#         return [
#             {"action": "open", "app": app},
#             {"action": "click", "text": "Create"},
#             {"action": "click", "text": "Project"},
#             {"action": "fill", "field": "Project name", "val": title},
#             {"action": "submit"},
#             {"action": "assert", "token": title},
#         ]

#     # --- Linear: your working flow ---
#     if app == "Linear" and obj == "project":
#         section = "Projects"
#         click_text = "New project"
#         field = "Name"
#         assert_token = "Project"

#         return [
#             {"action": "open", "app": app},
#             {"action": "goto", "section": section},
#             {"action": "click", "text": click_text},
#             {"action": "fill", "field": field, "val": title},
#             {"action": "submit"},
#             {"action": "assert", "token": assert_token},
#         ]

#     # --- Generic fallback for other cases ---
#     section = f"{obj}s" if obj else None
#     click_text = f"new {obj}" if obj else "new"
#     field = "name"
#     assert_token = "created"

#     steps = [{"action": "open", "app": app}]
#     if section:
#         steps.append({"action": "goto", "section": section})

#     steps.extend(
#         [
#             {"action": "click", "text": click_text},
#             {"action": "fill", "field": field, "val": title},
#             {"action": "submit"},
#             {"action": "assert", "token": assert_token},
#         ]
#     )
#     return steps


def _steps_filter(obj: str, app: str, criteria: str):
    return [
        {"action": "open", "app": app},
        {"action": "goto", "section": f"{obj}s"},
        {"action": "click", "text": "filter"},
        {"action": "fill", "field": "query", "val": criteria or "<AUTO_FILTER>"},
        {"action": "submit"},
        {"action": "assert", "token": "filtered"},
    ]


def _steps_update(obj: str, app: str, name: str):
    return [
        {"action": "open", "app": app},
        {"action": "goto", "section": f"{obj}s"},
        {"action": "click", "text": name or f"target {obj}"},
        {"action": "fill", "field": "value", "val": "<NEW_VALUE>"},
        {"action": "submit"},
        {"action": "assert", "token": "updated"},
    ]


def _steps_delete(obj: str, app: str, name: str):
    return [
        {"action": "open", "app": app},
        {"action": "goto", "section": f"{obj}s"},
        {"action": "click", "text": name or f"target {obj}"},
        {"action": "click", "text": "delete"},
        {"action": "submit"},
        {"action": "assert", "token": "deleted"},
    ]


def _steps_open(obj: str, app: str):
    return [
        {"action": "open", "app": app},
        {"action": "goto", "section": f"{obj}s"},
        {"action": "assert", "token": obj},
    ]


# ---------------------------
# EXTRACTION HELPERS
# ---------------------------
# def extract_possible_name(prompt: str, obj: str | None):
#     if not obj:
#         return None

#     tokens = prompt.lower().split()
#     if obj in tokens:
#         idx = tokens.index(obj)
#         if idx + 1 < len(tokens):
#             return " ".join(tokens[idx + 1:])

#     return None

# def extract_possible_name(prompt: str, obj: str | None, app: str | None = None):
#     if not obj:
#         return None

#     tokens = prompt.lower().split()

#     if obj not in tokens:
#         return None

#     idx = tokens.index(obj)
#     # Everything after the object word, e.g. "project"
#     name_tokens = tokens[idx + 1 :]

#     if not name_tokens:
#         return None

#     # Remove a trailing "in <app>" / "on <app>" / "at <app>" / "for <app>"
#     if app:
#         app_l = app.lower()
#         if len(name_tokens) >= 2:
#             if (
#                 name_tokens[-1] == app_l
#                 and name_tokens[-2] in {"in", "on", "at", "for"}
#             ):
#                 name_tokens = name_tokens[:-2]

#     # Strip leading filler words (in case user wrote "a project called X")
#     while name_tokens and name_tokens[0] in {"in", "on", "at", "the", "a", "an", "called","name"}:
#         name_tokens = name_tokens[1:]
#     print(name_tokens)

#     if not name_tokens:
#         return None

#     return " ".join(name_tokens)
def extract_possible_name(prompt: str, obj: str | None, app: str | None = None):
    if not obj:
        return None

    tokens = prompt.lower().split()

    if obj not in tokens:
        return None

    idx = tokens.index(obj)
    # Everything after the object word, e.g. "project"
    name_tokens = tokens[idx + 1 :]

    if not name_tokens:
        return None

    # 1) Remove a trailing "in <app>" / "on <app>" / "at <app>" / "for <app>"
    if app:
        app_l = app.lower()
        if len(name_tokens) >= 2:
            if (
                name_tokens[-1] == app_l
                and name_tokens[-2] in {"in", "on", "at", "for"}
            ):
                name_tokens = name_tokens[:-2]

    if not name_tokens:
        return None

    # 2) If we see markers like "name", "named", "called", "title" inside,
    #    only keep what comes AFTER the marker.
    markers = {"name", "named", "called", "title"}
    for j, tok in enumerate(name_tokens):
        if tok in markers and j + 1 < len(name_tokens):
            name_tokens = name_tokens[j + 1 :]
            break

    # 3) Strip leading filler words
    while name_tokens and name_tokens[0] in {"in", "on", "at", "the", "a", "an", "called"}:
        name_tokens = name_tokens[1:]

    # 4) Also drop any leading app token just in case
    if app:
        app_l = app.lower()
        while name_tokens and name_tokens[0] == app_l:
            name_tokens = name_tokens[1:]

    if not name_tokens:
        return None

    return " ".join(name_tokens)

def extract_filter_value(prompt: str) -> str | None:
    """
    Extremely simple heuristic: grab text after 'by' or 'with'.
    e.g. 'filter issues in Linear by priority high' -> 'priority high'
    """
    lower = prompt.lower()
    for kw in [" by ", " with "]:
        if kw in lower:
            return lower.split(kw, 1)[1].strip() or None
    return None
