## Python

- Do not add comments to code; write code that is clear without them.
- Keep `__init__.py` files thin; implementation belongs in modules.

## Instructions

- Agent-facing instructions (prompts, skills) must not reference anything outside the agent's workspace: no host paths, repo layout, or external services.

## Documentation

- Write instructions in your own words rather than quoting the user verbatim.
- Do not state what is gitignored; `.gitignore` is the source of truth.
- Do not explain how the system works by pointing at files; describe the behavior directly.
