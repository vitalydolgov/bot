"""Local stand-in for the hosted control plane: a SQLite store the worker polls.

`agents serve` registers the agent with the hosted control plane and polls its
task queue; sessions and their events live on the service. This package is the
same shape without the service: a SQLite file holds the agent registry, the
sessions, the command queue and the event log, and the worker polls it.
Sessions are journaled to disk, so a later `webui` resumes the latest one.

    uv run local-agents serve           # register every profile found in ~/.bots/profiles/ and poll for work
    uv run local-agents serve --profile grad   # serve only grad
    uv run local-agents webui           # serve a web client at http://127.0.0.1:8000/
    uv run local-agents webui --new     # start a fresh session
"""

import os

os.environ.setdefault("AGENTS_SDK_EXPERIMENTAL_WARNINGS", "0")

import argparse
import asyncio
import sys
from pathlib import Path

from .webui import webui
from .worker import serve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="Register the agent(s) and poll for work.")
    serve_parser.add_argument("--path", type=Path, default=Path("."))
    serve_parser.add_argument("--profile", default=None, help="Serve only this profile instead of all discovered profiles.")

    webui_parser = sub.add_parser("webui", help="Serve a web client for a served agent.")
    webui_parser.add_argument("agent", nargs="?", default="bot")
    webui_parser.add_argument("--port", type=int, default=8000)
    webui_parser.add_argument("--new", action="store_true", help="Start a fresh session.")
    webui_parser.add_argument("--resume", default=None, help="Resume a specific session by id.")

    args = parser.parse_args()
    if args.command == "serve":
        try:
            asyncio.run(serve(args.path, args.profile))
        except KeyboardInterrupt:
            pass
    elif args.command == "webui":
        sys.exit(webui(args.agent, args.port, args.new, args.resume))


if __name__ == "__main__":
    main()
