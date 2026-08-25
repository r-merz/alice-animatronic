from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResearchSource:
    title: str = ""
    url: str = ""
    source_type: str = "webpage"
    notes: str = ""


@dataclass
class ResearchSession:
    topic: str
    status: str = "planning"
    queries: list[str] = field(
        default_factory=list
    )
    sources: list[ResearchSource] = field(
        default_factory=list
    )
    findings: list[str] = field(
        default_factory=list
    )


class AliceResearchManager:
    def __init__(self):
        self.active_session = None

    def start_research(
        self,
        topic: str,
    ) -> ResearchSession:
        topic = str(
            topic or ""
        ).strip()

        if not topic:
            raise ValueError(
                "Research topic cannot be empty."
            )

        session = ResearchSession(
            topic=topic,
        )

        self.active_session = session

        return session