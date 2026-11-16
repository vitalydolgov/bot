import shutil
from pathlib import Path

from config import BOT_DIR
from mistralai import agents

SKILLS_DIR = BOT_DIR / "skills"
BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent / "instructions" / "skills"


def _seed_skills() -> None:
    if SKILLS_DIR.is_dir() or not BUILTIN_SKILLS_DIR.is_dir():
        return
    shutil.copytree(BUILTIN_SKILLS_DIR, SKILLS_DIR)


def load_skills() -> list[agents.LocalSkillBundle]:
    _seed_skills()
    if not SKILLS_DIR.is_dir():
        return []
    return [
        agents.LocalSkillBundle.from_directory(path)
        for path in sorted(SKILLS_DIR.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    ]
