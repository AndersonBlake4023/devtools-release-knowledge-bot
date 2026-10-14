from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .infrai_knowledge import InfraiError, InfraiKnowledgeIndex
from .release_diagnostics import DiagnosticAnswer, IncidentQuestion, answer_incident

app = FastAPI(title="Developer Tools Knowledge Bot")


@app.post("/diagnostics", response_model=DiagnosticAnswer)
def diagnose(request: IncidentQuestion) -> DiagnosticAnswer:
    index = InfraiKnowledgeIndex()
    try:
        return answer_incident(request, index)
    except InfraiError as error:
        caller_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=caller_status, detail=str(error)) from error
    finally:
        index.close()
