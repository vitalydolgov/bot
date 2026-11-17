from pathlib import Path
from typing import Annotated

from mistralai import agents
from pydantic import Field

from config import BOT_DIR, BOT_ROOT

MEMORY_PATH = (BOT_DIR or BOT_ROOT) / "MEMORY.md"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "instructions" / "prompts" / "memory.md"


def read_memory_text() -> str:
    try:
        return MEMORY_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def memory_instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


@agents.tool(model_access="direct")
def read_memory() -> str:
    """Read the current contents of your persistent memory file."""
    content = read_memory_text().strip()
    return content if content else "(memory is empty)"


@agents.tool(model_access="direct")
def remember(note: Annotated[str, Field(description="The fact or preference to remember, one line.")]) -> str:
    """Append a note to your persistent memory file so it is remembered across turns and sessions."""
    note = note.strip()
    if not note:
        return "Nothing to remember: the note was empty."
    existing = read_memory_text()
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with MEMORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{prefix}- {note}\n")
    return f"Remembered: {note}"


@agents.tool(model_access="direct")
def forget(note: Annotated[str, Field(description="Text identifying the entries to forget; every line containing this text (case-insensitive) is removed.")]) -> str:
    """Remove entries from your persistent memory file that match the given text."""
    query = " ".join(note.split()).lower()
    if not query:
        return "Nothing to forget: the query was empty."
    kept: list[str] = []
    removed: list[str] = []
    for line in read_memory_text().splitlines():
        if query in line.lower():
            removed.append(line)
        else:
            kept.append(line)
    if not removed:
        return f"No memory entries match '{note.strip()}'."
    MEMORY_PATH.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return "Forgot:\n" + "\n".join(removed)


@agents.tool(model_access="direct")
def write_memory(content: Annotated[str, Field(description="The full new contents of your persistent memory file.")]) -> str:
    """Replace the whole contents of your persistent memory file, for editing or removing existing entries."""
    MEMORY_PATH.write_text(content if content.endswith("\n") or not content else content + "\n", encoding="utf-8")
    return "Memory updated."


MEMORY_TOOLS = [read_memory, remember, forget, write_memory]
