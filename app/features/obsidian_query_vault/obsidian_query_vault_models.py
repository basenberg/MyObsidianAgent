"""Pydantic models for obsidian_query_vault_tool responses."""

from pydantic import BaseModel


class NoteInfo(BaseModel):
    """Summary information about a vault note returned in query results.

    Attributes:
        path: Relative path from vault root (e.g., "Projects/ML Project.md").
        title: Note title — first H1 heading or filename stem.
        relevance: Relevance score 0.0-1.0. 1.0 for non-ranked results.
        excerpt: Matching context excerpt (~200 chars). Populated in detailed mode only.
        tags: Tags from YAML frontmatter. Populated in detailed mode only.
        modified: ISO 8601 last-modified timestamp. Populated in detailed mode only.
    """

    path: str
    title: str
    relevance: float = 1.0
    excerpt: str | None = None
    tags: list[str] | None = None
    modified: str | None = None


class QueryResult(BaseModel):
    """Response model for obsidian_query_vault_tool.

    Attributes:
        results: List of matching notes (may be empty).
        total_found: Total matches before limit was applied.
        truncated: True if results were cut off at the limit.
        query_type: The query_type that was executed (for agent reference).
        suggestion: Actionable guidance when results are empty or truncated.
    """

    results: list[NoteInfo]
    total_found: int
    truncated: bool
    query_type: str
    suggestion: str | None = None
