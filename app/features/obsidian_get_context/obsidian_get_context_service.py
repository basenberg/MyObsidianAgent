"""GetContextService — business logic for all vault context reading operations.

This module is deliberately decoupled from Pydantic AI (no RunContext dependency),
making every operation directly unit-testable without constructing an agent run.

The service is instantiated per-request inside obsidian_get_context_tools.py:
    service = GetContextService(VaultManager(ctx.deps.vault_path))
    result = service.dispatch(context_type, **kwargs)
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.features.obsidian_get_context.obsidian_get_context_models import (
    BacklinkInfo,
    ContextResult,
    NoteContent,
)
from app.shared.vault.vault_manager import VaultManager

logger = get_logger(__name__)


class GetContextService:
    """Business logic for Obsidian vault context-reading operations.

    Wraps VaultManager read methods with optional context enrichment
    (metadata, backlinks, related notes). All public methods return ContextResult.

    Args:
        vault: Initialised VaultManager pointed at the vault root.
    """

    def __init__(self, vault: VaultManager) -> None:
        """Initialise with a VaultManager instance.

        Args:
            vault: VaultManager instance for the target vault.
        """
        self._vault = vault
        self._vault_root: Path = vault._root  # pyright: ignore[reportPrivateUsage]

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _build_note_content(
        self,
        path: Path,
        include_metadata: bool,
        concise: bool,
    ) -> NoteContent:
        """Read a note and return a NoteContent instance.

        Args:
            path: Absolute path to the note.
            include_metadata: If True, populate metadata from frontmatter.
            concise: If True, truncate content to first 200 words.

        Returns:
            Populated NoteContent.

        Raises:
            ValueError: If file does not exist.
        """
        content = self._vault.read_file(path)
        if concise:
            words = content.split()
            content = " ".join(words[:200]) + ("…" if len(words) > 200 else "")

        word_count = len(content.split())
        title = self._vault.get_title(path)
        path_str = self._vault.to_relative(path)
        metadata: dict[str, Any] | None = None
        if include_metadata:
            parsed = self._vault.parse_frontmatter(path)
            metadata = parsed if parsed else None

        return NoteContent(
            path=path_str,
            title=title,
            content=content,
            metadata=metadata,
            word_count=word_count,
        )

    def _find_backlinks(self, target: Path, limit: int) -> list[BacklinkInfo]:
        """Find notes that link to target using wiki-link search.

        Searches for [[stem]] and [[title]] patterns, deduplicates by path,
        and excludes the target note itself.

        Args:
            target: Absolute path to the target note.
            limit: Maximum number of backlinks to return.

        Returns:
            List of BacklinkInfo for notes linking to target.
        """
        stem = target.stem
        title = self._vault.get_title(target)
        target_relative = self._vault.to_relative(target)

        seen_paths: set[str] = set()
        results: list[BacklinkInfo] = []

        for search_term in [f"[[{stem}]]", f"[[{title}]]"]:
            if len(results) >= limit:
                break
            matches = self._vault.search_content(search_term, limit=limit * 2)
            for note_path, excerpt in matches:
                relative = self._vault.to_relative(note_path)
                if relative == target_relative or relative in seen_paths:
                    continue
                seen_paths.add(relative)
                results.append(
                    BacklinkInfo(
                        note_path=relative,
                        note_title=self._vault.get_title(note_path),
                        context=excerpt,
                    )
                )
                if len(results) >= limit:
                    break

        return results

    def _resolve_daily_note(self, date_str: str) -> Path:
        """Resolve a daily note path from a date string.

        Tries candidate paths in order:
        1. Daily Notes/{date}.md
        2. Journal/{date}.md
        3. {date}.md (vault root)

        Args:
            date_str: ISO date string like "2025-01-15" or "today".

        Returns:
            Absolute Path to the daily note.

        Raises:
            ValueError: If the daily note cannot be found in any candidate path.
        """
        if date_str == "today":
            date_str = datetime.datetime.now(tz=datetime.UTC).date().isoformat()

        candidates = [
            self._vault_root / "Daily Notes" / f"{date_str}.md",
            self._vault_root / "Journal" / f"{date_str}.md",
            self._vault_root / f"{date_str}.md",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise ValueError(
            f"Daily note not found for '{date_str}'. "
            f"Searched: 'Daily Notes/{date_str}.md', 'Journal/{date_str}.md', '{date_str}.md'. "
            f"Use obsidian_query_vault_tool with query_type='search_by_metadata' to find daily notes."
        )

    # -------------------------------------------------------------------------
    # Public context operations
    # -------------------------------------------------------------------------

    def read_note(
        self,
        target: str | None,
        include_metadata: bool,
        include_backlinks: bool,
        max_related: int,
        concise: bool,
    ) -> ContextResult:
        """Read a single note with optional metadata and backlinks.

        Args:
            target: Vault-relative note path. Required.
            include_metadata: If True, populate metadata and metadata_summary.
            include_backlinks: If True, find notes linking to this note.
            max_related: Max backlinks to include.
            concise: If True, truncate content to first 200 words.

        Returns:
            ContextResult with primary_note and optional backlinks.
        """
        if not target:
            error_msg = "read_note requires a target path. Example: target='Projects/Alpha.md'"
            return ContextResult(
                primary_note=NoteContent(path="", title="error", content=error_msg, word_count=0),
                context_type="read_note",
                error=error_msg,
            )

        abs_path = self._vault.get_note_path(target)
        try:
            primary = self._build_note_content(abs_path, include_metadata, concise)
        except (ValueError, OSError) as exc:
            error_msg = str(exc)
            return ContextResult(
                primary_note=NoteContent(
                    path=target, title="error", content=error_msg, word_count=0
                ),
                context_type="read_note",
                error=error_msg,
            )

        backlinks: list[BacklinkInfo] | None = None
        if include_backlinks:
            found = self._find_backlinks(abs_path, limit=max_related)
            backlinks = found if found else None

        metadata_summary: dict[str, Any] | None = primary.metadata if include_metadata else None

        result = ContextResult(
            primary_note=primary,
            backlinks=backlinks,
            metadata_summary=metadata_summary,
            context_type="read_note",
        )
        result.token_estimate = len(result.model_dump_json()) // 4
        return result

    def read_multiple(
        self,
        targets: list[str] | None,
        include_metadata: bool,
        concise: bool,
    ) -> ContextResult:
        """Read multiple notes, returning the first as primary and rest as related.

        Args:
            targets: List of vault-relative note paths. First is primary_note.
            include_metadata: If True, populate metadata on each note.
            concise: If True, truncate content to first 200 words.

        Returns:
            ContextResult with primary_note and related_notes.
        """
        if not targets:
            error_msg = "read_multiple requires at least one path in the targets list."
            return ContextResult(
                primary_note=NoteContent(path="", title="error", content=error_msg, word_count=0),
                context_type="read_multiple",
                error=error_msg,
            )

        skipped: list[str] = []
        notes: list[NoteContent] = []
        for t in targets:
            try:
                abs_path = self._vault.get_note_path(t)
                notes.append(self._build_note_content(abs_path, include_metadata, concise))
            except (ValueError, OSError):
                skipped.append(t)
                logger.warning("vault.context.note_skipped", path=t)

        if not notes:
            error_msg = f"None of the requested notes could be read. Missing: {skipped}"
            return ContextResult(
                primary_note=NoteContent(path="", title="error", content=error_msg, word_count=0),
                context_type="read_multiple",
                error=error_msg,
            )

        warning: str | None = f"Skipped missing notes: {skipped}" if skipped else None
        result = ContextResult(
            primary_note=notes[0],
            related_notes=notes[1:] if len(notes) > 1 else None,
            context_type="read_multiple",
            error=warning,
        )
        result.token_estimate = len(result.model_dump_json()) // 4
        return result

    def gather_related(
        self,
        target: str | None,
        include_metadata: bool,
        max_related: int,
        concise: bool,
    ) -> ContextResult:
        """Read a note and its tag-related notes.

        Args:
            target: Vault-relative note path. Required.
            include_metadata: If True, populate metadata on each note.
            max_related: Max related notes to include.
            concise: If True, truncate content to first 200 words.

        Returns:
            ContextResult with primary_note and related_notes.
        """
        if not target:
            error_msg = "gather_related requires a target path. Example: target='Projects/Alpha.md'"
            return ContextResult(
                primary_note=NoteContent(path="", title="error", content=error_msg, word_count=0),
                context_type="gather_related",
                error=error_msg,
            )

        abs_path = self._vault.get_note_path(target)
        try:
            primary = self._build_note_content(abs_path, include_metadata, concise)
        except (ValueError, OSError) as exc:
            error_msg = str(exc)
            return ContextResult(
                primary_note=NoteContent(
                    path=target, title="error", content=error_msg, word_count=0
                ),
                context_type="gather_related",
                error=error_msg,
            )

        scored = self._vault.find_related_by_tags(abs_path, limit=max_related)
        if not scored:
            fm = self._vault.parse_frontmatter(abs_path)
            tags = fm.get("tags", [])
            if not tags:
                error_msg = (
                    "No tags found on target note — gather_related requires frontmatter tags."
                )
            else:
                error_msg = "No related notes found — no other notes share the same tags."
            result = ContextResult(
                primary_note=primary,
                related_notes=[],
                context_type="gather_related",
                error=error_msg,
            )
            result.token_estimate = len(result.model_dump_json()) // 4
            return result

        related: list[NoteContent] = []
        for rel_path, _ in scored:
            try:
                related.append(self._build_note_content(rel_path, include_metadata, concise))
            except (ValueError, OSError):
                continue

        result = ContextResult(
            primary_note=primary,
            related_notes=related if related else None,
            context_type="gather_related",
        )
        result.token_estimate = len(result.model_dump_json()) // 4
        return result

    def daily_note(
        self,
        date_str: str | None,
        include_metadata: bool,
        concise: bool,
    ) -> ContextResult:
        """Read a daily note by date.

        Args:
            date_str: ISO date "2025-01-15" or "today". Defaults to "today" if None.
            include_metadata: If True, populate metadata on the note.
            concise: If True, truncate content to first 200 words.

        Returns:
            ContextResult with primary_note set to the daily note, or error if not found.
        """
        resolved_date = date_str or "today"
        try:
            note_path = self._resolve_daily_note(resolved_date)
        except ValueError as exc:
            error_msg = str(exc)
            return ContextResult(
                primary_note=NoteContent(path="", title="error", content=error_msg, word_count=0),
                context_type="daily_note",
                error=error_msg,
            )

        primary = self._build_note_content(note_path, include_metadata, concise)
        result = ContextResult(
            primary_note=primary,
            context_type="daily_note",
        )
        result.token_estimate = len(result.model_dump_json()) // 4
        return result

    def note_with_backlinks(
        self,
        target: str | None,
        include_metadata: bool,
        max_related: int,
        concise: bool,
    ) -> ContextResult:
        """Read a note and all notes that link back to it via wiki-links.

        Args:
            target: Vault-relative note path. Required.
            include_metadata: If True, populate metadata on primary note.
            max_related: Max backlinks to include.
            concise: If True, truncate content to first 200 words.

        Returns:
            ContextResult with primary_note and backlinks.
        """
        if not target:
            error_msg = (
                "note_with_backlinks requires a target path. "
                "Example: target='Concepts/Zettelkasten.md'"
            )
            return ContextResult(
                primary_note=NoteContent(path="", title="error", content=error_msg, word_count=0),
                context_type="note_with_backlinks",
                error=error_msg,
            )

        abs_path = self._vault.get_note_path(target)
        try:
            primary = self._build_note_content(abs_path, include_metadata, concise)
        except (ValueError, OSError) as exc:
            error_msg = str(exc)
            return ContextResult(
                primary_note=NoteContent(
                    path=target, title="error", content=error_msg, word_count=0
                ),
                context_type="note_with_backlinks",
                error=error_msg,
            )
        found_backlinks = self._find_backlinks(abs_path, limit=max_related)

        result = ContextResult(
            primary_note=primary,
            backlinks=found_backlinks if found_backlinks else None,
            context_type="note_with_backlinks",
        )
        result.token_estimate = len(result.model_dump_json()) // 4
        return result

    # -------------------------------------------------------------------------
    # Dispatch
    # -------------------------------------------------------------------------

    def dispatch(
        self,
        context_type: str,
        target: str | None = None,
        targets: list[str] | None = None,
        date: str | None = None,
        include_metadata: bool = True,
        include_backlinks: bool = False,
        max_related: int = 3,
        concise: bool = False,
    ) -> ContextResult:
        """Route a context_type string to the appropriate service method.

        Args:
            context_type: One of the 5 supported context type literals.
            target: Single-target vault-relative path.
            targets: Multi-target paths (read_multiple).
            date: Date string for daily_note ("today" or ISO format).
            include_metadata: Whether to include frontmatter in NoteContent.
            include_backlinks: Whether to find backlinks (read_note only).
            max_related: Maximum related notes or backlinks to include.
            concise: Whether to truncate content to first 200 words.

        Returns:
            ContextResult from the dispatched method.

        Raises:
            ValueError: If context_type is not one of the 5 known values.
        """
        if context_type == "read_note":
            return self.read_note(target, include_metadata, include_backlinks, max_related, concise)
        if context_type == "read_multiple":
            return self.read_multiple(targets, include_metadata, concise)
        if context_type == "gather_related":
            return self.gather_related(target, include_metadata, max_related, concise)
        if context_type == "daily_note":
            return self.daily_note(date, include_metadata, concise)
        if context_type == "note_with_backlinks":
            return self.note_with_backlinks(target, include_metadata, max_related, concise)

        raise ValueError(
            f"Unknown context_type: '{context_type}'. "
            "Valid values: read_note, read_multiple, gather_related, daily_note, note_with_backlinks."
        )
