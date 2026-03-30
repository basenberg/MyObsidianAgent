"""Domain models for vault file system entities."""

from pydantic import BaseModel, Field


class VaultNote(BaseModel):
    """A single markdown note discovered in the vault.

    Attributes:
        path: Relative path from vault root (e.g., "Projects/ML Project.md").
        title: Note title — first H1 heading, or filename stem if no heading.
        tags: List of tags from YAML frontmatter.
        modified_iso: ISO 8601 last-modified timestamp string.
        size_bytes: File size in bytes.
    """

    path: str
    title: str
    tags: list[str] = Field(default_factory=list)
    modified_iso: str = ""
    size_bytes: int = 0


class VaultFolder(BaseModel):
    """A folder in the vault.

    Attributes:
        path: Relative path from vault root (e.g., "Projects/2025").
        file_count: Number of markdown files directly inside this folder.
        subfolder_count: Number of immediate subdirectories.
    """

    path: str
    file_count: int = 0
    subfolder_count: int = 0
