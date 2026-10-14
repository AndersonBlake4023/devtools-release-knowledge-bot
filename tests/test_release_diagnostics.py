from typing import Any

from devtools_kb.release_diagnostics import IncidentQuestion, answer_incident


class ReleaseEvidenceGateway:
    def embed(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["Why are signed uploads failing after today's release?"]
        return [[0.2, 0.7, 0.1]]

    def query(self, embedding: list[float], team: str, service: str) -> list[dict[str, Any]]:
        assert embedding == [0.2, 0.7, 0.1]
        assert (team, service) == ("tooling", "artifact-registry")
        return [
            {
                "id": "release-note",
                "metadata": {
                    "note_id": "release-8841",
                    "title": "Signed-upload smoke check",
                    "text": "The release failed its signed-upload smoke check.",
                    "event_kind": "release",
                    "release_outcome": "failed",
                    "rollback_command": "releasectl rollback artifact-registry --to 2026.09.05",
                },
            },
            {
                "id": "build-note",
                "metadata": {
                    "note_id": "build-8841",
                    "title": "Compilation result",
                    "text": "The build completed compilation.",
                    "event_kind": "build",
                    "release_outcome": "not_applicable",
                },
            },
        ]

    def rerank(self, question: str, candidates: list[str]) -> list[dict[str, Any]]:
        assert question.startswith("Why are signed uploads")
        assert len(candidates) == 2
        return [{"index": 0, "score": 0.97}, {"index": 1, "score": 0.42}]


def test_failed_release_evidence_selects_rollback() -> None:
    result = answer_incident(
        IncidentQuestion(
            team="tooling",
            service="artifact-registry",
            question="Why are signed uploads failing after today's release?",
        ),
        ReleaseEvidenceGateway(),
    )

    assert result.recommendation == "rollback_release"
    assert result.rollback_command == "releasectl rollback artifact-registry --to 2026.09.05"
    assert result.evidence[0].note_id == "release-8841"
