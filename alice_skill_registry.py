from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class AliceSkillRegistry:
    def __init__(
        self,
        registry_path: Path,
    ) -> None:
        self.registry_path = (
            Path(registry_path).resolve()
        )

    def _default_registry(
        self,
    ) -> dict[str, Any]:
        return {
            "version": 1,
            "skills": [],
        }

    def load(
        self,
    ) -> dict[str, Any]:
        if not self.registry_path.exists():
            return self._default_registry()

        try:
            with self.registry_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return self._default_registry()

            skills = data.get(
                "skills",
                [],
            )

            if not isinstance(skills, list):
                skills = []

            return {
                "version": 1,
                "skills": skills,
            }

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ) as error:
            print(
                "Could not load Alice skill registry:",
                error,
            )

            return self._default_registry()

    def save(
        self,
        registry: dict[str, Any],
    ) -> None:
        self.registry_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            self.registry_path.with_suffix(
                ".json.tmp"
            )
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                registry,
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temporary_path,
            self.registry_path,
        )

    def register_skill(
        self,
        *,
        skill_id: str,
        name: str,
        description: str,
        changed_files: list[str],
        proposal_id: str,
        test_summary: str,
    ) -> dict[str, Any]:
        registry = self.load()

        entry = {
            "skill_id": skill_id,
            "name": name,
            "description": description,
            "changed_files": changed_files,
            "proposal_id": proposal_id,
            "test_summary": test_summary,
            "installed_at": time.time(),
            "enabled": True,
        }

        existing_skills = [
            skill
            for skill in registry["skills"]
            if (
                isinstance(skill, dict)
                and skill.get("skill_id")
                != skill_id
            )
        ]

        existing_skills.append(
            entry
        )

        registry["skills"] = (
            existing_skills
        )

        self.save(
            registry
        )

        return entry