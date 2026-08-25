from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class AliceUpdateValidator:
    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = (
            Path(project_root).resolve()
        )

    def validate_file(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        file_path = Path(
            file_path
        ).resolve()

        suffix = file_path.suffix.lower()

        if suffix == ".py":
            return self._validate_python(
                file_path
            )

        if suffix == ".json":
            return self._validate_json(
                file_path
            )

        if suffix == ".js":
            return self._validate_javascript(
                file_path
            )

        if suffix in {
            ".html",
            ".css",
        }:
            return {
                "success": True,
                "command": "basic-file-check",
                "output": (
                    "No dedicated parser is "
                    "configured for this file type."
                ),
            }

        return {
            "success": False,
            "command": "unsupported",
            "output": (
                f"Unsupported file type: {suffix}"
            ),
        }

    def _validate_python(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "py_compile",
                    str(file_path),
                ],
                cwd=str(
                    self.project_root
                ),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "command": "python -m py_compile",
                "output": (
                    "Python validation timed out."
                ),
            }

        return {
            "success": (
                result.returncode == 0
            ),
            "command": "python -m py_compile",
            "output": (
                result.stderr.strip()
                or result.stdout.strip()
                or "Python syntax check passed."
            ),
        }

    def _validate_json(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        try:
            with file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                json.load(file)

            return {
                "success": True,
                "command": "json.load",
                "output": (
                    "JSON syntax check passed."
                ),
            }

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            return {
                "success": False,
                "command": "json.load",
                "output": str(error),
            }

    def _validate_javascript(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [
                    "node",
                    "--check",
                    str(file_path),
                ],
                cwd=str(
                    self.project_root
                ),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        except FileNotFoundError:
            return {
                "success": False,
                "command": "node --check",
                "output": (
                    "Node.js was not found."
                ),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "command": "node --check",
                "output": (
                    "JavaScript validation timed out."
                ),
            }

        return {
            "success": (
                result.returncode == 0
            ),
            "command": "node --check",
            "output": (
                result.stderr.strip()
                or result.stdout.strip()
                or "JavaScript syntax check passed."
            ),
        }