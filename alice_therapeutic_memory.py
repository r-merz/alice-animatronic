from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import json 
import os
from pathlib import Path


@dataclass
class TherapeuticMemory:
    memory_type: str
    statement: str
    confidence: float
    evidence_count: int
    evidence: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class AliceTherapeuticMemoryManager:

    def __init__(
        self,
        memory_file: str | Path = "alice_therapeutic_memory.json",
    ):
        self.memory_file = Path(memory_file)

        self.pending_patterns: dict[
            str,
            list[dict[str, Any]]
        ] = {}

        self.memories: list[
            TherapeuticMemory
        ] = []

        self.load()
    def load(self) -> None:

        if not self.memory_file.exists():
            return

        try:
            data = json.loads(
                self.memory_file.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(data, dict):
                return

            stored_memories = data.get(
                "memories",
                [],
            )

            if not isinstance(
                stored_memories,
                list,
            ):
                return

            loaded = []

            for item in stored_memories:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                statement = str(
                    item.get(
                        "statement",
                        "",
                    )
                ).strip()

                if not statement:
                    continue

                loaded.append(
                    TherapeuticMemory(
                        memory_type=str(
                            item.get(
                                "memory_type",
                                "support_pattern",
                            )
                        ),
                        statement=statement,
                        confidence=float(
                            item.get(
                                "confidence",
                                0.5,
                            )
                        ),
                        evidence_count=int(
                            item.get(
                                "evidence_count",
                                0,
                            )
                        ),
                        evidence=list(
                            item.get(
                                "evidence",
                                [],
                            )
                        ),
                        created_at=str(
                            item.get(
                                "created_at",
                                "",
                            )
                        ),
                        updated_at=str(
                            item.get(
                                "updated_at",
                                "",
                            )
                        ),
                    )
                )

            self.memories = loaded

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as error:

            print(
                "Could not load therapeutic memory:",
                f"{type(error).__name__}: {error}",
            )

    def save(self) -> None:

        payload = {
            "version": 1,
            "memories": [
                {
                    "memory_type":
                        memory.memory_type,

                    "statement":
                        memory.statement,

                    "confidence":
                        memory.confidence,

                    "evidence_count":
                        memory.evidence_count,

                    "evidence":
                        memory.evidence,

                    "created_at":
                        memory.created_at,

                    "updated_at":
                        memory.updated_at,
                }
                for memory in self.memories
            ],
        }

        temporary_path = (
            self.memory_file
            .with_suffix(
                self.memory_file.suffix
                + ".tmp"
            )
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            os.replace(
                temporary_path,
                self.memory_file,
            )

        except OSError as error:

            print(
                "Could not save therapeutic memory:",
                error,
            )
    def observe_reflection(
        self,
        reflection: dict[str, Any],
    ) -> None:

        if not reflection:
            return

        candidate = reflection.get(
            "memory_candidate"
        )

        if not candidate:
            return

        candidate = str(
            candidate
        ).strip()

        if not candidate:
            return

        confidence = float(
            reflection.get(
                "confidence",
                0.0,
            )
        )

        if confidence < 0.65:
            return

        evidence_entry = {
            "strategy": reflection.get(
                "support_strategy_used"
            ),
            "outcome": reflection.get(
                "outcome"
            ),
            "reasoning": reflection.get(
                "reasoning"
            ),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        bucket = self.pending_patterns.setdefault(
            candidate,
            [],
        )

        bucket.append(
            evidence_entry
        )

        if len(bucket) >= 2:
            self.promote_pattern(
                candidate
            )

    def promote_pattern(
        self,
        candidate: str,
    ) -> None:

        evidence = self.pending_patterns.get(
            candidate,
            [],
        )

        if len(evidence) < 2:
            return

        existing = next(
            (
                memory
                for memory in self.memories
                if memory.statement == candidate
            ),
            None,
        )

        if existing is not None:
            existing.evidence.extend(
                evidence
            )

            existing.evidence_count = len(
                existing.evidence
            )

            existing.confidence = min(
                0.95,
                0.6
                + (
                    existing.evidence_count
                    * 0.08
                ),
            )

            existing.updated_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

        else:
            memory = TherapeuticMemory(
                memory_type=(
                    "support_pattern"
                ),
                statement=candidate,
                confidence=min(
                    0.95,
                    0.6
                    + len(
                        evidence
                    )
                    * 0.08,
                ),
                evidence_count=len(
                    evidence
                ),
                evidence=list(
                    evidence
                ),
            )

            self.memories.append(
                memory
            )

        self.pending_patterns.pop(
            candidate,
            None,
        )
        self.save()

    def delete_memory(
        self,
        statement: str,
    ) -> bool:

        statement = str(
            statement or ""
        ).strip()

        original_count = len(
            self.memories
        )

        self.memories = [
            memory
            for memory in self.memories
            if memory.statement != statement
        ]

        changed = (
            len(self.memories)
            != original_count
        )

        if changed:
            self.save()

        return changed

    def clear_all(self) -> None:

        self.memories.clear()
        self.pending_patterns.clear()

        self.save()

    def get_relevant_memories(
        self,
        limit: int = 5,
    ) -> list[dict[str, Any]]:

        sorted_memories = sorted(
            self.memories,
            key=lambda memory: (
                memory.confidence,
                memory.evidence_count,
            ),
            reverse=True,
        )

        return [
            {
                "memory_type":
                    memory.memory_type,
                "statement":
                    memory.statement,
                "confidence":
                    memory.confidence,
                "evidence_count":
                    memory.evidence_count,
            }
            for memory in sorted_memories[
                :limit
            ]
        ]