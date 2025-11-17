from pathlib import Path
import yaml
import re
from typing import Dict, List, Any, Optional
import string
from difflib import get_close_matches
import re

CONFIG_DIR = Path(__file__).parent / "config"



def _load_configs():
    with open(CONFIG_DIR / "intents.yaml") as f:
        intents_cfg = yaml.safe_load(f)

    with open(CONFIG_DIR / "app_names.yaml") as f:
        app_names = yaml.safe_load(f)["apps"]

    return intents_cfg, app_names



def _normalize(prompt: str) -> str:
    prompt = prompt.lower()
    prompt = prompt.translate(str.maketrans("", "", string.punctuation))
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt



def _detect_app(prompt: str, apps: List[str]) -> Optional[str]:
    tokens = re.findall(r"[a-zA-Z]+", prompt.lower())
    apps_lower = [a.lower() for a in apps]

    for token in tokens:
        match = get_close_matches(token, apps_lower, n=1, cutoff=0.7)
        if match:
            idx = apps_lower.index(match[0])
            return apps[idx]

    return None



def _detect_intent_object(prompt: str, intents_cfg):
    tokens = re.findall(r"[a-zA-Z]+", prompt.lower())

    
    intent_vocab: Dict[str, str] = {}
    for intent_name, info in intents_cfg.get("intents", {}).items():
        for v in info.get("verbs", []):
            intent_vocab[v.lower()] = intent_name

   
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

    if intent == "open":
        return _steps_open(obj, app)

    return [
        {"action": "open", "app": app},
        {"action": "assert", "token": "opened"},
    ]


def _write_steps_yaml(steps, run_dir: Path):
    with open(run_dir / "steps.yaml", "w") as f:
        yaml.safe_dump(steps, f, sort_keys=False)



def plan(prompt: str, run_dir: Path, logger) -> None:
    intents_cfg, app_names = _load_configs()
    norm = _normalize(prompt)

    app = _detect_app(norm, app_names)
    intent, obj = _detect_intent_object(norm, intents_cfg)

    logger.info(f"Parsed: intent={intent}, object={obj}, app={app}")

    steps = _build_steps(intent, obj, app, prompt)
    _write_steps_yaml(steps, run_dir)

    logger.info(f"Planner wrote {len(steps)} steps → {run_dir/'steps.yaml'}")



def _steps_create(obj: str | None, app: str | None, name: str | None):
    title = name or "<AUTO_NAME>"


    if app == "Notion" and obj == "database":
       return [
        {"action": "open", "app": app, "state_label": "notion_home"},

        {"action": "click", "text": "New page", "state_label": "notion_new_page_clicked"},

        {"action": "click", "text": "Database", "state_label": "notion_db_template_open"},

        {
            "action": "click",
            "text": "Empty",
            "state_label": "notion_empty_db_selected"
        },

        {
            "action": "fill",
            "field": "New page",
            "val": title,
            "state_label": "notion_db_title_filled"
        },

        {
            "action": "assert",
            "token": title,
            "state_label": "notion_db_created"
        },
    ]
    if app == "Notion" and obj == "page":
        return [
            {"action": "open", "app": app, "state_label": "notion_home"},
            {"action": "click", "text": "New page", "state_label": "notion_new_page_clicked"},
            {"action": "fill", "field": "New page", "val": title, "state_label": "notion_title_filled"},
            {"action": "assert", "token": title, "state_label": "notion_page_created"},
        ]


    if app == "Linear" and obj == "project":
        section = "Projects"
        click_text = "New project"
        field = "Name"
        assert_token = "Project"

        return [
          
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

            {"action": "click", "text": "Create issue", "state_label": "issue_created_button_clicked"},

            {"action": "assert", "token": title, "state_label": "issue_created"},
        ]


    section = f"{obj}s" if obj else None
    click_text = f"new {obj}" if obj else "new"
    field = "name"
    assert_token = "created"

    
    steps: List[Dict[str, Any]] = [{"action": "open", "app": app, "state_label": "app_open"}]
    if section:
        steps.append({"action": "goto", "section": section, "state_label": f"{section.lower()}_list"})

    steps.extend(
        [
            {"action": "click", "text": click_text, "state_label": f"new_{obj}_click" if obj else "new_item_click"},
            {"action": "fill", "field": field, "val": title, "state_label": f"{obj}_name_filled" if obj else "name_filled"},
            {"action": "submit", "state_label": "submit_clicked"},
            {"action": "assert", "token": assert_token, "state_label": f"{obj}_created" if obj else "item_created"},
        ]
    )

    return steps

   
def _steps_filter(obj: str, app: str, criteria: str | None):
    criteria = (criteria or "").strip()

    steps: List[Dict[str, Any]] = [
        {"action": "open", "app": app, "state_label": f"{app.lower()}_home"},
        {"action": "goto", "section": f"{obj}s", "state_label": f"{obj}s_list"},
        {"action": "click", "text": "Filter", "state_label": "filter_panel_open"},
    ]

    if criteria:
        keywords = re.findall(r"[a-zA-Z]+", criteria.lower())
        for kw in keywords:
            steps.append(
                {
                    "action": "click",
                    "text": kw,           
                    "state_label": f"filter_kw_{kw}",
                }
            )
    steps.append(
        {
            "action": "assert",
            "token": "Filter",         
            "state_label": "filter_result_visible",
        }
    )

    return steps



def _steps_open(obj: str, app: str):
    return [
        {"action": "open", "app": app},
        {"action": "goto", "section": f"{obj}s"},
        {"action": "assert", "token": obj},
    ]


def extract_possible_name(prompt: str, obj: str | None, app: str | None = None):
    if not obj:
        return None

    tokens = prompt.lower().split()

    if obj not in tokens:
        return None

    idx = tokens.index(obj)

    name_tokens = tokens[idx + 1 :]

    if not name_tokens:
        return None

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

   
    markers = {"name", "named", "called", "title"}
    for j, tok in enumerate(name_tokens):
        if tok in markers and j + 1 < len(name_tokens):
            name_tokens = name_tokens[j + 1 :]
            break

   
    while name_tokens and name_tokens[0] in {"in", "on", "at", "the", "a", "an", "called"}:
        name_tokens = name_tokens[1:]

    
    if app:
        app_l = app.lower()
        while name_tokens and name_tokens[0] == app_l:
            name_tokens = name_tokens[1:]

    if not name_tokens:
        return None

    return " ".join(name_tokens)

def extract_filter_value(prompt: str) -> str | None:
   
    lower = prompt.lower()
    for kw in [" by ", " with "]:
        if kw in lower:
            return lower.split(kw, 1)[1].strip() or None
    return None

