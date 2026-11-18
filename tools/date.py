from datetime import datetime

from mistralai import agents


@agents.tool(model_access="direct")
def current_datetime() -> str:
    """Return the current local date and time with timezone, in ISO 8601 format."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


DATE_TOOLS = [current_datetime]
