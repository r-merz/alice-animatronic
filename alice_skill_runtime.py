from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any


class AliceSkillRuntime:
    def __init__(
        self,
        project_root: Path,
        skill_registry,
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()

        self.skill_registry = (
            skill_registry
        )

        self.loaded_skills: list[
            dict[str, Any]
        ] = []

    def reload(self) -> None:
        self.loaded_skills = []

        entries = self._registry_entries()

        for entry in entries:
            try:
                loaded = self._load_entry(
                    entry
                )

            except Exception as error:
                print(
                    "Could not load Alice skill:",
                    {
                        "entry": entry,
                        "error": (
                            f"{type(error).__name__}: "
                            f"{error}"
                        ),
                    },
                )
                continue

            self.loaded_skills.append(
                loaded
            )

    def _registry_entries(
        self,
    ) -> list[dict[str, Any]]:
        loader = getattr(
            self.skill_registry,
            "load",
            None,
        )

        if callable(loader):
            data = loader()

        else:
            registry_path = Path(
                self.skill_registry.registry_path
            )

            if not registry_path.exists():
                return []

            import json

            data = json.loads(
                registry_path.read_text(
                    encoding="utf-8"
                )
            )

        if isinstance(data, dict):
            entries = data.get(
                "skills",
                [],
            )

        elif isinstance(data, list):
            entries = data

        else:
            entries = []

        return [
            item
            for item in entries
            if isinstance(
                item,
                dict,
            )
        ]

    def _load_entry(
        self,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        relative_path = str(
            entry.get(
                "path",
                entry.get(
                    "file",
                    "",
                ),
            )
        ).strip()

        if not relative_path:
            files = entry.get(
                "files",
                [],
            )

            if isinstance(files, list):
                relative_path = next(
                    (
                        str(path)
                        for path in files
                        if str(path).endswith(
                            (
                                "_skill.py",
                                "_tool.py",
                            )
                        )
                    ),
                    "",
                )

        if not relative_path:
            raise ValueError(
                "Registry entry has no skill file."
            )

        module_path = (
            self.project_root
            / relative_path
        ).resolve()

        module_path.relative_to(
            self.project_root
        )

        if not module_path.exists():
            raise FileNotFoundError(
                module_path
            )

        module_name = (
            "alice_dynamic_skill_"
            + module_path.stem
        )

        spec = (
            importlib.util
            .spec_from_file_location(
                module_name,
                module_path,
            )
        )

        if (
            spec is None
            or spec.loader is None
        ):
            raise ImportError(
                f"Could not load {relative_path}."
            )

        module = (
            importlib.util
            .module_from_spec(
                spec
            )
        )

        spec.loader.exec_module(
            module
        )

        can_handle = getattr(
            module,
            "can_handle",
            None,
        )

        run = getattr(
            module,
            "run",
            None,
        )

        if not callable(can_handle):
            raise TypeError(
                f"{relative_path} must define "
                "can_handle(text)."
            )

        if not callable(run):
            raise TypeError(
                f"{relative_path} must define "
                "run(text, context)."
            )

        return {
            "entry": entry,
            "module": module,
            "can_handle": can_handle,
            "run": run,
        }

    def handle(
        self,
        text: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        for skill in self.loaded_skills:
            can_handle = skill[
                "can_handle"
            ]

            try:
                matched = bool(
                    can_handle(
                        text
                    )
                )

            except Exception as error:
                print(
                    "Skill routing failed:",
                    error,
                )
                continue

            if not matched:
                continue

            run = skill["run"]

            result = run(
                text,
                context,
            )

            if inspect.isawaitable(
                result
            ):
                raise TypeError(
                    "Async skills are not supported "
                    "by this runtime."
                )

            if not isinstance(
                result,
                dict,
            ):
                raise TypeError(
                    "Skill run() must return a "
                    "dictionary."
                )

            return result

        return None