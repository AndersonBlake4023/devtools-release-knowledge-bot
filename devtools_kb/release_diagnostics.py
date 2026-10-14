from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class KnowledgeNote(BaseModel):
    note_id: str = Field(min_length=1)
    team: str = Field(min_length=1)
    service: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    event_kind: Literal["build", "release", "diagnostic"]
    release_outcome: Literal["passed", "failed", "not_applicable"]
    rollback_command: str | None = None


class IncidentQuestion(BaseModel):
    team: str = Field(min_length=1)
    service: str = Field(min_length=1)
    question: str = Field(min_length=3)


class Evidence(BaseModel):
    note_id: str
    title: str
    text: str


class DiagnosticAnswer(BaseModel):
    recommendation: Literal["rollback_release", "continue_diagnosis", "no_evidence"]
    answer: str
    rollback_command: str | None
    evidence: list[Evidence]


def answer_incident(question: IncidentQuestion, gateway: Any) -> DiagnosticAnswer:
    embedding = gateway.embed([question.question])[0]
    matches = gateway.query(embedding, question.team, question.service)
    candidates = [str(match.get("metadata", {}).get("text", "")) for match in matches]
    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        return DiagnosticAnswer(
            recommendation="no_evidence",
            answer="No scoped build or release note matched this question.",
            rollback_command=None,
            evidence=[],
        )

    ranked = gateway.rerank(question.question, candidates)
    ordered_matches = []
    for result in ranked:
        index = int(result["index"])
        if 0 <= index < len(matches):
            ordered_matches.append(matches[index])

    evidence = [
        Evidence(
            note_id=str(item.get("metadata", {}).get("note_id", item.get("id", "unknown"))),
            title=str(item.get("metadata", {}).get("title", "Untitled note")),
            text=str(item.get("metadata", {}).get("text", "")),
        )
        for item in ordered_matches
    ]
    top = ordered_matches[0].get("metadata", {}) if ordered_matches else {}
    should_rollback = (
        top.get("event_kind") == "release"
        and top.get("release_outcome") == "failed"
        and bool(top.get("rollback_command"))
    )
    return DiagnosticAnswer(
        recommendation="rollback_release" if should_rollback else "continue_diagnosis",
        answer=evidence[0].text if evidence else "No ranked evidence was returned.",
        rollback_command=str(top["rollback_command"]) if should_rollback else None,
        evidence=evidence,
    )
