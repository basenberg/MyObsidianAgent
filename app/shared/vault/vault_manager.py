"""VaultManager — file system abstraction for Obsidian vault operations.

All vault feature tools use this class. Instantiate per-request:
    vault = VaultManager(ctx.deps.vault_path)

Design: pure pathlib, stdlib only, fully type-annotated, errors are actionable strings.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class VaultManager:
    """File system abstraction for an Obsidian markdown vault.

    Args:
        vault_path: Absolute path to vault root directory.

    Raises:
        ValueError: If vault_path does not exist or is not a directory.
    """

    def __init__(self, vault_path: str) -> None:
        """Initialize VaultManager and validate the vault root.

        Args:
            vault_path: Absolute path to vault root directory.

        Raises:
            ValueError: If vault_path does not exist or is not a directory.
        """
        self._root = Path(vault_path)
        if not self._root.exists():
            raise ValueError(
                f"Vault path does not exist: '{vault_path}'. "
                f"Set VAULT_PATH env var to the correct path."
            )
        if not self._root.is_dir():
            raise ValueError(f"Vault path is not a directory: '{vault_path}'.")

    # -------------------------------------------------------------------------
    # File discovery
    # -------------------------------------------------------------------------

    def list_markdown_files(self, folder: str = "", recursive: bool = True) -> list[Path]:
        """List markdown files under a vault folder.

        Args:
            folder: Vault-relative folder path. Empty string for vault root.
            recursive: If True, search all subdirectories.

        Returns:
            Sorted list of absolute Path objects for .md files.

        Raises:
            ValueError: If folder does not exist within the vault.
        """
        base = self._root / folder if folder else self._root
        if not base.exists():
            raise ValueError(
                f"Folder not found: '{folder}'. "
                f"Use list_markdown_files(folder='') to see top-level structure."
            )
        pattern = "**/*.md" if recursive else "*.md"
        return sorted(base.glob(pattern))

    def list_folders(self, folder: str = "") -> list[Path]:
        """List immediate subdirectories under a vault folder.

        Args:
            folder: Vault-relative folder path. Empty string for vault root.

        Returns:
            Sorted list of absolute Path objects for directories (excludes hidden).

        Raises:
            ValueError: If folder does not exist within the vault.
        """
        base = self._root / folder if folder else self._root
        if not base.exists():
            raise ValueError(f"Folder not found: '{folder}'.")
        return sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))

    def get_recent_files(self, limit: int = 10) -> list[Path]:
        """Return markdown files sorted by modification time, newest first.

        Args:
            limit: Maximum number of files to return.

        Returns:
            List of absolute Path objects, most recently modified first.
        """
        all_files = list(self._root.glob("**/*.md"))
        return sorted(all_files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    def get_note_path(self, relative_path: str) -> Path:
        """Resolve a vault-relative path to an absolute Path.

        Args:
            relative_path: Path relative to vault root (e.g., "Projects/Alpha.md").

        Returns:
            Absolute Path to the note.
        """
        return self._root / relative_path

    # -------------------------------------------------------------------------
    # Content operations
    # -------------------------------------------------------------------------

    def read_file(self, path: Path) -> str:
        """Read full text content of a vault file.

        Args:
            path: Absolute path to the file.

        Returns:
            Full file content as string.

        Raises:
            ValueError: If file does not exist.
        """
        if not path.exists():
            raise ValueError(
                f"Note not found: '{self.to_relative(path)}'. "
                f"Use obsidian_query_vault_tool to find available notes."
            )
        return path.read_text(encoding="utf-8")

    def search_content(self, query: str, limit: int = 10) -> list[tuple[Path, str]]:
        """Case-insensitive keyword search across all vault markdown files.

        Args:
            query: Search string (case-insensitive substring match).
            limit: Maximum number of results to return.

        Returns:
            List of (path, excerpt) tuples for files containing the query.
        """
        query_lower = query.lower()
        results: list[tuple[Path, str]] = []

        for file_path in self._root.glob("**/*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError:
                continue

            if query_lower not in content.lower():
                continue

            excerpt = self._extract_excerpt(content, query)
            results.append((file_path, excerpt))

            if len(results) >= limit:
                break

        return results

    def find_related_by_tags(self, reference: Path, limit: int = 10) -> list[tuple[Path, int]]:
        """Find notes sharing tags with a reference note, ranked by overlap.

        Args:
            reference: Absolute path to the reference note.
            limit: Maximum number of related notes to return.

        Returns:
            List of (path, shared_tag_count) tuples, sorted by overlap descending.
        """
        ref_tags = set(self.parse_frontmatter(reference).get("tags", []))
        if not ref_tags:
            return []

        scored: list[tuple[Path, int]] = []
        for file_path in self._root.glob("**/*.md"):
            if file_path == reference:
                continue
            try:
                note_tags = set(self.parse_frontmatter(file_path).get("tags", []))
            except (OSError, ValueError):
                continue
            overlap = len(ref_tags & note_tags)
            if overlap > 0:
                scored.append((file_path, overlap))

        return sorted(scored, key=lambda t: t[1], reverse=True)[:limit]

    # -------------------------------------------------------------------------
    # Metadata operations
    # -------------------------------------------------------------------------

    def parse_frontmatter(self, path: Path) -> dict[str, Any]:
        """Parse YAML frontmatter from a markdown file.

        Uses a simple line-by-line parser — no PyYAML dependency.
        Handles scalar values, inline lists [a, b], and block lists (- item).

        Args:
            path: Absolute path to the markdown file.

        Returns:
            Dictionary of frontmatter key-value pairs. Returns {} if none found.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return {}

        if not content.startswith("---"):
            return {}

        end = content.find("\n---", 3)
        if end == -1:
            return {}

        front = content[3:end].strip()
        result: dict[str, Any] = {}
        current_key: str | None = None

        for line in front.splitlines():
            stripped = line.strip()

            # Block list item
            if stripped.startswith("- ") and current_key is not None:
                item = stripped[2:].strip().strip("\"'")
                existing = result.get(current_key)
                if isinstance(existing, list):
                    existing.append(item)  # pyright: ignore[reportUnknownMemberType]
                else:
                    result[current_key] = [item]
                continue

            if ":" not in stripped:
                continue

            key, _, raw_value = stripped.partition(":")
            key = key.strip()
            raw_value = raw_value.strip()
            current_key = key

            if not raw_value:
                # Block list follows — initialise empty list
                result[key] = []
            elif raw_value.startswith("[") and raw_value.endswith("]"):
                # Inline list: [a, b, c]
                items = [i.strip().strip("\"'") for i in raw_value[1:-1].split(",")]
                result[key] = [i for i in items if i]
            else:
                result[key] = raw_value.strip("\"'")

        return result

    def get_title(self, path: Path) -> str:
        """Extract note title: first H1 heading, or filename stem as fallback.

        Args:
            path: Absolute path to the markdown file.

        Returns:
            Title string — never empty.
        """
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
        except OSError:
            pass
        return path.stem

    def get_modified_iso(self, path: Path) -> str:
        """Return the file's last modification time as ISO 8601 UTC string.

        Args:
            path: Absolute path to the file.

        Returns:
            Datetime string in format "YYYY-MM-DDTHH:MM:SSZ".
        """
        t = time.gmtime(path.stat().st_mtime)
        return (
            f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T"
            f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}Z"
        )

    def to_relative(self, path: Path) -> str:
        """Convert an absolute path to a vault-relative string for display.

        Args:
            path: Absolute path within the vault.

        Returns:
            Relative path string from vault root, using forward slashes.
        """
        try:
            return str(path.relative_to(self._root))
        except ValueError:
            return str(path)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _extract_excerpt(self, content: str, query: str, context: int = 100) -> str:
        """Extract a ~200-char excerpt around the first query match.

        Args:
            content: Full file content.
            query: The search query to locate.
            context: Characters of context on each side of the match.

        Returns:
            Excerpt string, at most 200 characters.
        """
        idx = content.lower().find(query.lower())
        if idx == -1:
            return content[:200]
        start = max(0, idx - context)
        end = min(len(content), idx + len(query) + context)
        excerpt = content[start:end].replace("\n", " ").strip()
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(content):
            excerpt = excerpt + "..."
        return excerpt[:200]
