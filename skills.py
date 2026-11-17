import shutil
from pathlib import Path

from config import WORKSPACE_DIR

BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent / "instructions" / "skills"
SKILLS_DIR = WORKSPACE_DIR / ".agents" / "skills"


def seed_skills() -> None:
    if not BUILTIN_SKILLS_DIR.is_dir():
        return
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for path in BUILTIN_SKILLS_DIR.iterdir():
        target = SKILLS_DIR / path.name
        if path.is_dir() and not target.exists():
            shutil.copytree(path, target)
