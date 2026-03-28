"""Agent dependency injection container."""

from dataclasses import dataclass


@dataclass
class AgentDependencies:
    """Dependencies injected into vault_agent via RunContext.

    Passed as deps= at every agent.run() call. Tools access via ctx.deps.

    Attributes:
        request_id: HTTP request correlation ID for log tracing.
    """

    request_id: str = ""
