from pathlib import Path
import yaml
import re
import difflib 
from typing import Dict, List, Any
import string
from difflib import get_close_matches


CONFIG_DIR = Path(__file__).parent / "config"

def _load_configs():
    with open(CONFIG_DIR / "intents.yaml") as f:
        intents_cfg = yaml.safe_load(f)
    with open(CONFIG_DIR / "app_names.yaml") as f:
        app_names = yaml.safe_load(f)["apps"]
    return intents_cfg, app_names

def _normalize(prompt: str) -> str:
    # lowercase + squash spaces, etc.
    prompt=prompt.lower()
    prompt=prompt.translate(prompt.maketrans("", "", string.punctuation))

def _detect_app(prompt: str, apps: List[str]) -> str | None:
    # fuzzy-match words in prompt to app_names
    matching_apps= get_close_matches(prompt,apps,n=1, cutoff=0.6)

    return matching_apps

def _detect_intent_object(prompt: str, intents_cfg) -> tuple[str | None, str | None]:
    # build vocab from intents.yaml, fuzzy-match tokens to intent and object
    matching_intents = get_close_matches(prompt, intents_cfg, n=1, cutoff=0.6)
    return matching_intents

def _build_steps(intent: str | None,
                 obj: str | None,
                 app: str | None,
                 prompt: str) -> List[Dict[str, Any]]:
    # For now, handle a few simple combos:
    #   create + project
    #   filter + issue
    #   etc.
    # Always return 4–7 steps with only schema verbs.
    ...

def _write_steps_yaml(steps, run_dir: Path):
    ...

def plan(prompt: str, run_dir: Path, logger) -> None:
    intents_cfg, app_names = _load_configs()
    norm = _normalize(prompt)
    app = _detect_app(prompt, app_names)
    intent, obj = _detect_intent_object(norm, intents_cfg)
    steps = _build_steps(intent, obj, app, prompt)
    _write_steps_yaml(steps, run_dir)
    logger.info(f"Planner created {len(steps)} steps in {run_dir / 'steps.yaml'}")



def _steps_create(obj: str, app : str, name: str):
    return [
        {"action": "open", "app": app},
        {"action": "goto", "section": f"{obj}s"},      # projects, issues, pages
        {"action": "click", "text": f"new {obj}"},     # neutral
        {"action": "fill", "field": "name", "val": name or "<AUTO_NAME>"},
        {"action": "submit"},
        {"action": "assert", "token": "created"},
    ]

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



def extract_possible_name(prompt: str, obj: str):
    # If user types: "create project Test App"
    # find the word(s) after "project"
    tokens = prompt.lower().split()
    if obj in tokens:
        idx = tokens.index(obj)
        if idx + 1 < len(tokens):
            return " ".join(tokens[idx+1:])
    return None

