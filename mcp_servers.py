from dataclasses import asdict

from mistralai import agents

from config import MCP_SERVERS


def load_mcps() -> dict[str, agents.RemoteMCP]:
    servers: dict[str, agents.RemoteMCP] = {}
    for name, server in MCP_SERVERS.items():
        kwargs = {key: value for key, value in asdict(server).items() if value is not None}
        servers[name] = agents.RemoteMCP(**kwargs)
    return servers
