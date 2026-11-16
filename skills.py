from config import BOT_DIR
from mistralai import agents

SKILLS_DIR = BOT_DIR / "skills"


def load_skills() -> list[agents.LocalSkillBundle]:
    if not SKILLS_DIR.is_dir():
        return []
    return [
        agents.LocalSkillBundle.from_directory(path)
        for path in sorted(SKILLS_DIR.iterdir())
        if path.is_dir() and (path / "SKILL.md").is_file()
    ]
