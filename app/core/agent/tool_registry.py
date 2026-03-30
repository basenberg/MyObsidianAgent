"""Central tool registration hub for vault_agent.

Import this module exactly once — in app/main.py — to register all tools on
vault_agent. Each import below triggers the @vault_agent.tool decorator as a
side effect, registering the function on the agent singleton.

To add a new tool:
    1. Create app/features/<feature>/obsidian_<feature>_tools.py
    2. Decorate the tool function with @vault_agent.tool
    3. Add an import line below (with # noqa: F401)
"""

# Registered tools (import order = registration order):
import app.features.obsidian_query_vault.obsidian_query_vault_tools  # noqa: F401  # pyright: ignore[reportUnusedImport]

# Future tools — uncomment as implemented:
# import app.features.obsidian_get_context.obsidian_get_context_tools
# import app.features.obsidian_vault_manager.obsidian_vault_manager_tools
