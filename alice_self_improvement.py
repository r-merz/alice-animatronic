from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any
import threading
import subprocess
import sys


from alice_update_validator import (
    AliceUpdateValidator,
)


VALID_STATES = {
    "proposed",
    "staging_approved",
    "staged",
    "validation_failed",
    "validated",
    "installation_approved",
    "installed",
    "rejected",
    "rolled_back",
}


class AliceSelfImprovementManager:
    def __init__(
        self,
        *,
        project_root: Path,
        staging_root: Path,
        backup_root: Path,
        state_file: Path,
        skill_registry,
    ) -> None:
        self.project_root = (
            Path(project_root).resolve()
        )

        self.staging_root = (
            Path(staging_root).resolve()
        )

        self.backup_root = (
            Path(backup_root).resolve()
        )

        self.state_file = (
            Path(state_file).resolve()
        )

        self.skill_registry = (
            skill_registry
        )
        self.lock = threading.RLock()

        self.validator = (
            AliceUpdateValidator(
                self.project_root
            )
        )

        self.allowed_suffixes = {
            ".py",
            ".js",
            ".html",
            ".css",
            ".json",
        }

        self.protected_parts = {
            ".git",
            ".venv",
            "__pycache__",
            ".env",
            ".alice_updates",
            ".alice_backups",
        }

        self.staging_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.backup_root.mkdir(
            parents=True,
            exist_ok=True,
        )
    def record_staging_failure(
        self,
        error_message: str,
    ) -> dict[str, Any]:
        with self.lock:
            state = self.load_state()

            proposal = state.get(
                "active_proposal"
            )

            if not isinstance(
                proposal,
                dict,
            ):
                raise RuntimeError(
                    "There is no active proposal."
                )

            proposal["last_staging_error"] = str(
                error_message or ""
            ).strip()

            proposal["last_staging_failure_at"] = (
                time.time()
            )

            state["active_proposal"] = proposal

            self.save_state(
                state
            )

            return proposal
    def resolve_project_file(
        self,
        relative_path: str,
    ) -> Path:
        normalized = str(
            relative_path or ""
        ).strip()

        if not normalized:
            raise ValueError(
                "A project path is required."
            )

        candidate = (
            self.project_root
            / normalized
        ).resolve()

        try:
            candidate.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise PermissionError(
                "The requested path is outside "
                "the Alice project."
            ) from error

        relative = candidate.relative_to(
            self.project_root
        )

        if any(
            part in self.protected_parts
            for part in relative.parts
        ):
            raise PermissionError(
                f"Protected project path: {relative}"
            )

        if (
            candidate.suffix.lower()
            not in self.allowed_suffixes
        ):
            raise PermissionError(
                "This file type cannot be "
                "self-modified."
            )

        return candidate
    def load_state(
        self,
    ) -> dict[str, Any]:
        if not self.state_file.exists():
            return {
                "active_proposal": None,
                "history": [],
            }

        try:
            with self.state_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise TypeError(
                    "Improvement state is not "
                    "a JSON object."
                )

            return {
                "active_proposal": data.get(
                    "active_proposal"
                ),
                "history": data.get(
                    "history",
                    [],
                ),
            }

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            return {
                "active_proposal": None,
                "history": [],
            }

    def save_state(
        self,
        state: dict[str, Any],
    ) -> None:
        temporary_path = (
            self.state_file.with_suffix(
                ".json.tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                state,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_path,
            self.state_file,
        )
    def create_proposal(
        self,
        *,
        title: str,
        skill_name: str,
        description: str,
        requested_files: list[str],
        acceptance_tests: list[str] | None = None,
        risks: list[str] | None = None,
        requires_restart: bool = True,
    ) -> dict[str, Any]:
        with self.lock:
            state = self.load_state()

            if state.get(
                "active_proposal"
            ):
                raise RuntimeError(
                    "Another improvement proposal "
                    "is already active."
                )

            normalized_files = []

            for relative_path in requested_files:
                relative_path = str(
                    relative_path or ""
                ).strip()

                if not relative_path:
                    continue

                self.resolve_project_file(
                    relative_path
                )

                normalized_files.append(
                    relative_path
                )

            if not normalized_files:
                raise ValueError(
                    "The proposal must include at "
                    "least one requested file."
                )

            if (
                len(normalized_files)
                != len(set(normalized_files))
            ):
                raise ValueError(
                    "The proposal contains duplicate "
                    "requested files."
                )

            proposal_id = (
                "improvement-"
                f"{int(time.time())}-"
                f"{uuid.uuid4().hex[:8]}"
            )

            proposal = {
                "proposal_id": proposal_id,
                "state": "proposed",
                "title": str(
                    title or skill_name
                ).strip(),
                "skill_name": str(
                    skill_name
                ).strip(),
                "description": str(
                    description
                ).strip(),
                "requested_files": (
                    normalized_files
                ),
                "acceptance_tests": [
                    str(test).strip()
                    for test in (
                        acceptance_tests
                        or []
                    )
                    if str(test).strip()
                ],
                "risks": [
                    str(risk).strip()
                    for risk in (
                        risks
                        or []
                    )
                    if str(risk).strip()
                ],
                "requires_restart": bool(
                    requires_restart
                ),
                "created_at": time.time(),
                "staged_files": [],
                "diffs": {},
                "validation": [],
                "backup_directory": "",
                "installed_at": None,
            }

            if not proposal["skill_name"]:
                raise ValueError(
                    "A skill name is required."
                )

            if not proposal["description"]:
                raise ValueError(
                    "A proposal description is required."
                )

            state["active_proposal"] = (
                proposal
            )

            self.save_state(
                state
            )

            return proposal
    def _require_state(
        self,
        proposal: dict[str, Any],
        required_state: str,
    ) -> None:
        if proposal.get("state") != required_state:
            raise RuntimeError(
                "Invalid improvement transition: "
                f"expected {required_state}, "
                f"found {proposal.get('state')}."
            )
    def stage_files(
        self,
        generated_files: list[dict[str, str]],
    ) -> dict[str, Any]:
        with self.lock: 
            state = self.load_state()

        proposal = state.get(
            "active_proposal"
        )

        if not isinstance(
            proposal,
            dict,
        ):
            raise RuntimeError(
                "There is no active proposal."
            )

        self._require_state(
            proposal,
            "staging_approved",
        )

        expected_paths = set(
            proposal["requested_files"]
        )

        supplied_paths = {
            str(item.get("path", "")).strip()
            for item in generated_files
            if isinstance(item, dict)
        }

        if supplied_paths != expected_paths:
            raise ValueError(
                "Generated file paths do not "
                "match the approved proposal."
            )

        proposal_directory = (
            self.staging_root
            / proposal["proposal_id"]
        )

        if proposal_directory.exists():
            shutil.rmtree(
                proposal_directory
            )

        proposal_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        diffs = {}
        staged_files = []

        for generated_file in generated_files:
            relative_path = str(
                generated_file["path"]
            ).strip()

            content = generated_file.get(
                "content"
            )

            if not isinstance(content, str):
                raise TypeError(
                    f"Generated content for "
                    f"{relative_path} is not text."
                )

            original_path = (
                self.resolve_project_file(
                    relative_path
                )
            )

            original_content = (
                original_path.read_text(
                    encoding="utf-8"
                )
                if original_path.exists()
                else ""
            )

            staged_path = (
                proposal_directory
                / relative_path
            ).resolve()

            staged_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            staged_path.write_text(
                content,
                encoding="utf-8",
            )

            diff = "\n".join(
                difflib.unified_diff(
                    original_content.splitlines(),
                    content.splitlines(),
                    fromfile=(
                        f"a/{relative_path}"
                    ),
                    tofile=(
                        f"b/{relative_path}"
                    ),
                    lineterm="",
                )
            )

            diffs[relative_path] = diff
            staged_files.append(
                relative_path
            )

        proposal["state"] = "staged"
        proposal["staged_files"] = (
            staged_files
        )
        proposal["diffs"] = diffs

        state["active_proposal"] = (
            proposal
        )

        self.save_state(
            state
        )

        return proposal
    def validate_staged(
        self,
    ) -> dict[str, Any]:
        with self.lock: 
            state = self.load_state()
        proposal = state.get(
            "active_proposal"
        )

        if not isinstance(
            proposal,
            dict,
        ):
            raise RuntimeError(
                "There is no active proposal."
            )

        self._require_state(
            proposal,
            "staged",
        )

        proposal_directory = (
            self.staging_root
            / proposal["proposal_id"]
        )

        results = []

        for relative_path in (
            proposal["staged_files"]
        ):
            staged_path = (
                proposal_directory
                / relative_path
            )

            result = (
                self.validator.validate_file(
                    staged_path
                )
            )

            results.append(
                {
                    "path": relative_path,
                    **result,
                }
            )
            test_files = [
            relative_path
            for relative_path
            in proposal["staged_files"]
            if (
                Path(
                    relative_path
                ).suffix.lower()
                == ".py"
                and Path(
                    relative_path
                ).name.startswith(
                    "test_"
                )
            )
        ]

        for test_file in test_files:
            test_path = (
                proposal_directory
                / test_file
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        test_path
                    ),
                ],
                cwd=str(
                    proposal_directory
                ),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            output = (
                completed.stdout
                + completed.stderr
            ).strip()

            results.append(
                {
                    "path": test_file,
                    "success": (
                        completed.returncode
                        == 0
                    ),
                    "output": (
                        output
                        or (
                            "Test completed "
                            "without output."
                        )
                    ),
                }
            )
            

        all_passed = all(
            result.get("success") is True
            for result in results
        )

        proposal["validation"] = results
        proposal["state"] = (
            "validated"
            if all_passed
            else "validation_failed"
        )

        state["active_proposal"] = (
            proposal
        )

        self.save_state(
            state
        )

        return proposal
    def approve_installation(
        self,
        proposal_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Record the user's explicit approval to install a validated update.
        """
        with self.lock:
            state = self.load_state()

            proposal = state.get(
                "active_proposal"
            )

            if not isinstance(
                proposal,
                dict,
            ):
                raise ValueError(
                    "There is no active improvement proposal."
                )

            current_proposal_id = str(
                proposal.get(
                    "proposal_id",
                    "",
                )
            ).strip()

            if (
                proposal_id is not None
                and str(proposal_id).strip()
                != current_proposal_id
            ):
                raise ValueError(
                    "Proposal ID does not match "
                    "the active proposal."
                )

            self._require_state(
                proposal,
                "validated",
            )

            proposal["state"] = (
                "installation_approved"
            )

            proposal["installation_approved_at"] = (
                time.time()
            )

            state["active_proposal"] = proposal
            self.save_state(state)

            return proposal

    def install(
        self,
    ) -> dict[str, Any]:
        with self.lock: 
            state = self.load_state()
        proposal = state.get(
            "active_proposal"
        )

        if not isinstance(
            proposal,
            dict,
        ):
            raise RuntimeError(
                "There is no active proposal."
            )

        self._require_state(
            proposal,
            "installation_approved",
        )

        proposal_directory = (
            self.staging_root
            / proposal["proposal_id"]
        )

        backup_directory = (
            self.backup_root
            / proposal["proposal_id"]
        )

        backup_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        installed_files = []

        try:
            for relative_path in (
                proposal["staged_files"]
            ):
                project_path = (
                    self.resolve_project_file(
                        relative_path
                    )
                )

                staged_path = (
                    proposal_directory
                    / relative_path
                )

                backup_path = (
                    backup_directory
                    / relative_path
                )

                backup_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                if project_path.exists():
                    shutil.copy2(
                        project_path,
                        backup_path,
                    )

                project_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                temporary_install = (
                    project_path.with_suffix(
                        project_path.suffix
                        + ".alice-install.tmp"
                    )
                )

                shutil.copy2(
                    staged_path,
                    temporary_install,
                )

                os.replace(
                    temporary_install,
                    project_path,
                )

                installed_files.append(
                    relative_path
                )

        except Exception:
            self._restore_backup(
                backup_directory,
                installed_files,
            )
            raise

        proposal["state"] = "installed"
        proposal["installed_at"] = (
            time.time()
        )
        proposal["backup_directory"] = (
            str(backup_directory)
        )

        validation_summary = "\n".join(
            (
                f"{item['path']}: "
                f"{'passed' if item['success'] else 'failed'}"
            )
            for item in proposal["validation"]
        )

        skill_entry = (
            self.skill_registry.register_skill(
                skill_id=proposal[
                    "proposal_id"
                ],
                name=proposal[
                    "skill_name"
                ],
                description=proposal[
                    "description"
                ],
                changed_files=installed_files,
                proposal_id=proposal[
                    "proposal_id"
                ],
                test_summary=(
                    validation_summary
                ),
            )
        )

        proposal["skill_entry"] = (
            skill_entry
        )

        history = state.setdefault(
            "history",
            [],
        )

        history.append(
            proposal
        )

        state["active_proposal"] = None

        self.save_state(
            state
        )

        return proposal
    def _restore_backup(
        self,
        backup_directory: Path,
        installed_files: list[str],
    ) -> None:
        for relative_path in installed_files:
            backup_path = (
                backup_directory
                / relative_path
            )

            project_path = (
                self.project_root
                / relative_path
            ).resolve()

            if backup_path.exists():
                project_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    backup_path,
                    project_path,
                )
    def reject_active_proposal(
        self,
        reason="Rejected by user.",
    ):
        with self.lock:
            state = self.load_state()

            proposal = state.get(
                "active_proposal"
            )

            if not proposal:
                raise ValueError(
                    "There is no active "
                    "improvement proposal."
                )

            proposal["state"] = "rejected"
            proposal["rejection_reason"] = str(
                reason
            ).strip()
            proposal["finished_at"] = time.time()

            state.setdefault(
                "history",
                []
            ).append(
                proposal
            )

            state["active_proposal"] = None

            self.save_state(
                state
            )

            staging_directory = (
                self.staging_root
                / proposal["proposal_id"]
            )

            if staging_directory.exists():
                shutil.rmtree(
                    staging_directory
                )

            return proposal
    def describe_active_proposal(
        self,
    ):
        state = self.load_state()

        proposal = state.get(
            "active_proposal"
        )

        if not proposal:
            return (
                "There is no active "
                "improvement proposal."
            )

        return (
            "Active improvement: "
            f"{proposal.get('title', 'Untitled')}. "
            "Proposal ID: "
            f"{proposal.get('proposal_id')}. "
            "State: "
            f"{proposal.get('state')}."
        )
    def revise_active_proposal(
        self,
        *,
        title: str,
        skill_name: str,
        description: str,
        requested_files: list[str],
        acceptance_tests: list[str] | None = None,
        risks: list[str] | None = None,
        requires_restart: bool = True,
    ) -> dict[str, Any]:
        """
        Replace the editable fields of the active proposal and reset it
        to the proposed state. Any stale staged files are discarded.
        """
        with self.lock:
            state = self.load_state()
            proposal = state.get(
                "active_proposal"
            )

            if not isinstance(
                proposal,
                dict,
            ):
                raise ValueError(
                    "There is no active improvement proposal to revise."
                )

            if proposal.get("state") in {
                "installed",
                "rejected",
                "rolled_back",
            }:
                raise RuntimeError(
                    "This proposal can no longer be revised."
                )

            normalized_files = []

            for relative_path in requested_files:
                relative_path = str(
                    relative_path or ""
                ).strip()

                if not relative_path:
                    continue

                self.resolve_project_file(
                    relative_path
                )

                normalized_files.append(
                    relative_path
                )

            if not normalized_files:
                raise ValueError(
                    "The revised proposal must include at least one file."
                )

            if len(normalized_files) != len(
                set(normalized_files)
            ):
                raise ValueError(
                    "The revised proposal contains duplicate files."
                )

            staging_directory = (
                self.staging_root
                / proposal["proposal_id"]
            )

            if staging_directory.exists():
                shutil.rmtree(
                    staging_directory
                )

            proposal.update(
                {
                    "state": "proposed",
                    "title": str(
                        title or skill_name
                    ).strip(),
                    "skill_name": str(
                        skill_name
                    ).strip(),
                    "description": str(
                        description
                    ).strip(),
                    "requested_files": normalized_files,
                    "acceptance_tests": [
                        str(test).strip()
                        for test in (
                            acceptance_tests
                            or []
                        )
                        if str(test).strip()
                    ],
                    "risks": [
                        str(risk).strip()
                        for risk in (
                            risks
                            or []
                        )
                        if str(risk).strip()
                    ],
                    "requires_restart": bool(
                        requires_restart
                    ),
                    "revised_at": time.time(),
                    "staged_files": [],
                    "diffs": {},
                    "validation": [],
                    "backup_directory": "",
                    "installed_at": None,
                }
            )

            if not proposal["skill_name"]:
                raise ValueError(
                    "A skill name is required."
                )

            if not proposal["description"]:
                raise ValueError(
                    "A proposal description is required."
                )

            state["active_proposal"] = proposal
            self.save_state(state)

            return proposal

    def approve_staging(
        self,
        proposal_id: str | None = None,
    ) -> dict:
        with self.lock: 
            state = self.load_state()

        proposal = state.get(
            "active_proposal"
        )

        if not proposal:
            raise ValueError(
                "There is no active improvement proposal."
            )

        current_proposal_id = str(
            proposal.get(
                "proposal_id",
                "",
            )
        ).strip()

        if (
            proposal_id is not None
            and str(proposal_id).strip()
            != current_proposal_id
        ):
            raise ValueError(
                "Proposal ID does not match "
                "the active proposal."
            )

        current_state = proposal.get(
            "state"
        )

        # Repeating the command after a generation or UI error should
        # resume staging instead of failing the state transition.
        if current_state == "staging_approved":
            return proposal

        if current_state != "proposed":
            raise ValueError(
                "Staging approval requires a proposed or "
                "already staging-approved improvement. "
                f"Current state: {current_state!r}."
            )

        proposal["state"] = (
            "staging_approved"
        )

        proposal["staging_approved_at"] = (
            time.time()
        )

        state["active_proposal"] = proposal

        self.save_state(
            state
        )

        return proposal
    def get_active_proposal(
        self,
    ) -> dict | None:
        state = self.load_state()

        proposal = state.get(
            "active_proposal"
        )

        if not isinstance(
            proposal,
            dict,
        ):
            return None

        return proposal