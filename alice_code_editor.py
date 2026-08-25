from __future__ import annotations

import difflib
import shutil
import subprocess

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CodePatch:
    file_path: Path
    original_text: str
    updated_text: str
    explanation: str

    def unified_diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.original_text.splitlines(
                    keepends=True
                ),
                self.updated_text.splitlines(
                    keepends=True
                ),
                fromfile=str(self.file_path),
                tofile=str(self.file_path),
            )
        )


class AliceCodeEditor:
    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = (
            project_root.resolve()
        )

        self.allowed_extensions = {
            ".py",
            ".html",
            ".css",
            ".js",
            ".json",
        }

        self.pending_patch: CodePatch | None = None

    def resolve_file(
        self,
        relative_path: str,
    ) -> Path:
        requested_path = (
            self.project_root
            / relative_path
        ).resolve()

        try:
            requested_path.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise PermissionError(
                "Alice may only edit files "
                "inside the project directory."
            ) from error

        if (
            requested_path.suffix.lower()
            not in self.allowed_extensions
        ):
            raise PermissionError(
                "That file type is not editable."
            )

        if not requested_path.exists():
            raise FileNotFoundError(
                requested_path
            )

        return requested_path

    def read_file(
        self,
        relative_path: str,
    ) -> str:
        file_path = self.resolve_file(
            relative_path
        )

        return file_path.read_text(
            encoding="utf-8"
        )

    def prepare_replacement(
        self,
        relative_path: str,
        old_text: str,
        new_text: str,
        explanation: str,
    ) -> CodePatch:
        file_path = self.resolve_file(
            relative_path
        )

        original_text = file_path.read_text(
            encoding="utf-8"
        )

        occurrence_count = (
            original_text.count(
                old_text
            )
        )

        if occurrence_count == 0:
            raise ValueError(
                "The requested source text "
                "was not found."
            )

        if occurrence_count > 1:
            raise ValueError(
                "The requested source text "
                "appears more than once. "
                "A more specific match is required."
            )

        updated_text = (
            original_text.replace(
                old_text,
                new_text,
                1,
            )
        )

        patch = CodePatch(
            file_path=file_path,
            original_text=original_text,
            updated_text=updated_text,
            explanation=explanation,
        )

        self.pending_patch = patch

        return patch

    def apply_pending_patch(
        self,
    ) -> Path:
        patch = self.pending_patch

        if patch is None:
            raise RuntimeError(
                "There is no pending patch."
            )

        timestamp = datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )

        backup_path = (
            patch.file_path.with_name(
                patch.file_path.name
                + f".backup-{timestamp}"
            )
        )

        shutil.copy2(
            patch.file_path,
            backup_path,
        )

        patch.file_path.write_text(
            patch.updated_text,
            encoding="utf-8",
        )

        try:
            self.validate_file(
                patch.file_path
            )

        except Exception:
            shutil.copy2(
                backup_path,
                patch.file_path,
            )

            raise

        self.pending_patch = None

        return backup_path

    def reject_pending_patch(
        self,
    ) -> None:
        self.pending_patch = None

    def validate_file(
        self,
        file_path: Path,
    ) -> None:
        suffix = file_path.suffix.lower()

        if suffix == ".py":
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "py_compile",
                    str(file_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        elif suffix == ".json":
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "json.tool",
                    str(file_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )