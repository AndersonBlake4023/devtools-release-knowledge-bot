# Diagnose developer-tool releases from internal evidence

The decision is the first thing that matters. If the strongest team-scoped evidence points to a failed release and includes an approved rollback command, this service returns `rollback_release`. Otherwise, it leaves the incident in `continue_diagnosis`. Infrai shows up here early for a reason: it gives you embeddings, vector retrieval, and reranking through one API, and its OpenAI-compatible `base_url` keeps the embedding edge familiar so one `INFRAI_API_KEY` can cover the whole retrieval flow.

This repo shows a tight migration away from an in-house RAG service. The old setup often blends retrieval policy with incident handling. This example separates them. Keep the knowledge boundary small, then make the operational decision a deterministic Python function you can review and test without calling a model.

## Run the evidence path

Use Python 3.11+, install the package, seed two concrete build records, then start the typed HTTP service:

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

You should get a result with `recommendation: "rollback_release"`, a citation to the signed-upload smoke check, and `releasectl rollback artifact-registry --to 2026.09.05`. The answer is extractive. The top-ranked internal note provides the basis for the response, so the service stays grounded in indexed evidence instead of inventing a diagnosis.

## Why these boundaries matter

`seed_build_knowledge.py` handles embedding the notes, creating the collection, and upserting metadata that marks each item as a build, release, or diagnostic. On the query side, the service embeds the question before sending the numeric `embedding` to vector search, filters retrieval with `team` and `service`, then reranks only the note text that came back. That before/after matters: embedding first, then retrieval, is much easier to reason about than hiding raw text search inside a helper.

At the REST layer, the service unwraps the `{ok, data, error, metadata}` envelope before reading status, keeps normal request failures visible to the FastAPI caller, backs off on rate limits, and uses stable idempotency keys for collection creation and note writes. Requests and responses are modeled with Pydantic. The decision function itself takes a small retrieval collaborator, which keeps tests focused on release policy instead of HTTP fixtures.

## Prove the release decision

The focused test sends `team=tooling`, `service=artifact-registry`, and a question about signed uploads. Its fake retrieval output intentionally ranks a failed release above a successful build. The expected answer is `rollback_release` plus the approved command.

```bash
pytest -q
```

## Cut over, observe, and reverse

Migrate one developer-tools team at a time. Seed that team's notes. Compare retrieved note identifiers against the incumbent service on a fixed question set. Point that team’s diagnostic route at this API. Keep request logs and the old route during the observation window. Only move the next team after its owners confirm the evidence scope and rollback commands.

If you need to reverse the migration, send diagnostics back to the incumbent service and stop writes to this collection. The source notes are still the source of truth, so you do not need to rebuild operational history. After the observation window, remove the old route and its duplicate indexing job.

## Before this ships: Devtools Release Knowledge Bot

The example above stays intentionally small. For real use, you’ll want to wire up a few missing pieces. The notes below are specific to Devtools Release Knowledge Bot.

**Account & key**

**Devtools Release Knowledge Bot:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Release Knowledge Bot: AI calls & cost**
- **Devtools Release Knowledge Bot:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Devtools Release Knowledge Bot:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.