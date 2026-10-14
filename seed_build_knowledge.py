from devtools_kb.infrai_knowledge import InfraiKnowledgeIndex
from devtools_kb.release_diagnostics import KnowledgeNote


NOTES = [
    KnowledgeNote(
        note_id="release-2026-09-06-auth",
        team="tooling",
        service="artifact-registry",
        title="Artifact registry release rejected signed uploads",
        text="Release 2026.09.06 failed its signed-upload smoke check. Roll back, then compare signer configuration with the previous release.",
        event_kind="release",
        release_outcome="failed",
        rollback_command="releasectl rollback artifact-registry --to 2026.09.05",
    ),
    KnowledgeNote(
        note_id="build-2026-09-06-auth",
        team="tooling",
        service="artifact-registry",
        title="Artifact registry build completed",
        text="Build 8841 completed compilation and package verification before release promotion.",
        event_kind="build",
        release_outcome="not_applicable",
    ),
]


def main() -> None:
    index = InfraiKnowledgeIndex()
    try:
        payloads = [note.model_dump(exclude_none=True) for note in NOTES]
        embeddings = index.embed([note.text for note in NOTES])
        index.create_collection(len(embeddings[0]))
        index.upsert(payloads, embeddings)
        print(f"Indexed {len(NOTES)} build and release notes.")
    finally:
        index.close()


if __name__ == "__main__":
    main()
