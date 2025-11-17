import os
import sys
import uuid
import logging
import datetime as dt
from pathlib import Path
from typing import Optional
from planner import plan
from executor import execute_plan
RUNS_DIR = Path(os.environ.get("RUNS_DIR", "./runs"))
MIN_PROMPT_LEN = int(os.environ.get("MIN_PROMPT_LEN", "4"))
MAX_PROMPT_LEN = int(os.environ.get("MAX_PROMPT_LEN", "500"))

def _utc_run_id() -> str:
    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{str(uuid.uuid4())[:8]}"

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

class CLI:
    @staticmethod
    def read_prompt() -> Optional[str]:
        try:
            raw = input("Enter task (or 'exit' to quit) > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return None

        if raw.lower() in {"exit", "quit"}:
            return None

        if not raw:
            print(f"Please enter a clearer prompt (≥ {MIN_PROMPT_LEN} chars).")
            return ""

        if len(raw) < MIN_PROMPT_LEN:
            print(f"Please enter a clearer prompt (≥ {MIN_PROMPT_LEN} chars).")
            return ""

        if len(raw) > MAX_PROMPT_LEN:
            print(f"Trimming prompt to {MAX_PROMPT_LEN} chars.")
            raw = raw[:MAX_PROMPT_LEN]

        return raw

    @staticmethod
    def create_run(prompt: str) -> tuple[str, Path, logging.Logger]:
        _ensure_dir(RUNS_DIR)
        run_id = _utc_run_id()
        run_dir = RUNS_DIR / run_id
        states_dir = run_dir / "states"
        _ensure_dir(run_dir)
        _ensure_dir(states_dir)

        (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

        logger = logging.getLogger(f"ui-state-{run_id}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
            fh = logging.FileHandler(run_dir / "run.log", mode="w", encoding="utf-8")
            fh.setFormatter(fmt)
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(fmt)
            logger.addHandler(fh)
            logger.addHandler(ch)

        (run_dir / "run.json").write_text(
            (
                '{\n'
                f'  "run_id": "{run_id}",\n'
                f'  "prompt": {repr(prompt)},\n'
                f'  "start_time_utc": "{dt.datetime.utcnow().isoformat()}Z",\n'
                '  "steps_count": null,\n'
                '  "states_count": null,\n'
                '  "outcome": null\n'
                '}\n'
            ),
            encoding="utf-8",
        )

        logger.info(f"Run created: {run_id}")
        logger.info(f"Artifacts → {run_dir.resolve()}")

        return run_id, run_dir, logger


if __name__ == "__main__":
    print("Hi! I am your UI State Capture System.")
    _ensure_dir(RUNS_DIR)

    last_prompt: Optional[str] = None
    while True:
        prompt = CLI.read_prompt()
        if prompt is None:
           
            break
        if prompt == "":
            
            continue
        if last_prompt and prompt == last_prompt:
            print("Note: same prompt as last run.")
        last_prompt = prompt

        run_id, run_dir, logger = CLI.create_run(prompt)
        
        plan(prompt=prompt, run_dir=run_dir, logger=logger)
        execute_plan(run_dir, logger)

        logger.info("Run setup complete (planner/executor will attach here).")
        print(f"Run {run_id} ready at: {run_dir}\n")
