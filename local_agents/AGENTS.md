## Development

- Run the tests with `uv run python -m unittest discover -s local_agents/tests` from the repository root.
- The tests exercise the model layer against a temporary store; they do not touch `~/.bots` or start the web server.
