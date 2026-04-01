"""Pydantic models for obsidian_get_context_tool responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class NoteContent(BaseModel):
    """Full content of a vault note with optional metadata.

    Attributes:
        path: Vault-relative path from vault root (e.g., "Projects/ML Project.md").
        title: Note title — first H1 heading or filename stem.
        content: Full note content (or first 200 words in concise mode).
        metadata: YAML frontmatter key-value pairs, or None if absent/not requested.
        word_count: Number of words in the returned content.
    """

    path: str
    title: str
    content: str
    metadata: dict[str, Any] | None = None
    word_count: int = 0


class BacklinkInfo(BaseModel):
    """A note that links to another note via wiki-link syntax.

    Attributes:
        note_path: Vault-relative path of the linking note.
        note_title: Title of the linking note.
        context: Surrounding text excerpt where the link appears.
    """

    note_path: str
    note_title: str
    context: str


class ContextResult(BaseModel):
    """Response model for obsidian_get_context_tool.

    Attributes:
        primary_note: The main note requested.
        related_notes: Additional notes for multi-note operations.
        backlinks: Notes that wiki-link to the primary note.
        metadata_summary: Compiled frontmatter from primary note.
        token_estimate: Rough token count of this response (len(json) // 4).
        context_type: The context_type that was executed (for agent reference).
        error: Actionable error message if the operation failed or was partial.
    """

    primary_note: NoteContent
    related_notes: list[NoteContent] | None = None
    backlinks: list[BacklinkInfo] | None = None
    metadata_summary: dict[str, Any] | None = None
    token_estimate: int = 0
    context_type: str = ""
    error: str | None = None
