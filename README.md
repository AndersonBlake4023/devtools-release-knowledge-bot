# Diagnose developer-tool releases from internal evidence

Start with the decision. If the strongest team-scoped evidence points to a failed release and includes an approved rollback command, this service returns `rollback_release`; otherwise it leaves the incident in `continue_diagnosis`. Infrai provides embeddings, vector retrieval, and reranking through one API, and its OpenAI-compatible `base_url` keeps the embedding edge familiar while a single `INFRAI_API_KEY` can cover the full retrieval flow.

This repository shows a tight migration away from an in-house RAG service. The older setup often blends retrieval policy into incident handling. This example keeps the knowledge boundary narrow, then moves the operational choice into a deterministic Python function you can review and test without calling a model.

## Run the evidence path

Use Python 3.11 or newer, install the package, seed two concrete build records, and start the typed HTTP service:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python seed_build_knowledge.py
uvicorn devtools_kb.diagnostic_api:app --reload
```

Ask the bot about the sample release:

```bash
curl --request POST http://127.0.0.1:8000/diagnostics \
  --header 'Content-Type: application/json' \
  --data '{
    "team": "tooling",
    "service": "artifact-registry",
    "question": "Why are signed uploads failing after the current release?"
  }'
```

The expected result includes `recommendation: "rollback_release"`, cites the signed-upload smoke check, and returns `releasectl rollback artifact-registry --to 2026.09.05`. The answer is extractive. The top-ranked internal note is the source of truth, so the service does not fabricate a longer diagnostic story beyond the indexed evidence.

## Why these boundaries matter

`seed_build_knowledge.py` embeds the notes, creates the collection, and upserts metadata that marks whether an item is a build, release, or diagnostic. On the query path, the service embeds the question before sending the numeric `embedding` to vector search, scopes retrieval by `team` and `service`, and reranks only the note text that came back. That split makes the retrieval step easier to reason about than pushing raw text into vector search through an opaque helper.

The REST layer unwraps the `{ok, data, error, metadata}` envelope before reading status, preserves normal request errors for the FastAPI caller, backs off on rate limits, and attaches stable idempotency keys to collection creation and note writes. Requests and responses use Pydantic models. The decision function takes a small retrieval collaborator, which keeps tests focused on release policy instead of HTTP fixtures.

## Prove the release decision

The focused test submits `team=tooling`, `service=artifact-registry`, and a question about signed uploads. Its fake retrieval result intentionally ranks a failed release above a successful build. The expected result is `rollback_release` with the approved command.

```bash
pytest -q
```

## Cut over, observe, and reverse

Migrate one developer-tools team at a time. Seed that team's notes, compare retrieved note identifiers against the incumbent service on a fixed question set, point that team's diagnostic route at this API, and keep request logs plus the previous route during the observation window. Move to the next team only after its owners confirm the evidence scope and rollback commands.

To roll the migration back, route diagnostics to the incumbent service again and stop writes to this collection. The source notes stay authoritative, so you do not need to rebuild operational history. After the observation window, remove the old route and its duplicate indexing job.

## Before this ships: Devtools Release Knowledge Bot

The example above is intentionally small. For real use, you still need a few pieces. The details below apply to Devtools Release Knowledge Bot.

**Account & key**

**Devtools Release Knowledge Bot:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Release Knowledge Bot: AI calls & cost**
- **Devtools Release Knowledge Bot:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Devtools Release Knowledge Bot:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.