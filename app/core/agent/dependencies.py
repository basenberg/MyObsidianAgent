"""Agent dependency injection container."""

from dataclasses import dataclass


@dataclass
class AgentDependencies:
    """Dependencies injected into vault_agent via RunContext.

    Passed as deps= at every agent.run() call. Tools access via ctx.deps.

    Attributes:
        request_id: HTTP request correlation ID for log tracing.
        vault_path: Absolute path to vault root — injected from config at request time.
    """

    request_id: str = ""
    vault_path: str = "/vault"
