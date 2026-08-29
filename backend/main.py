#fastapi core server setup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.services.agent_engine import run_sre_pipeline
from app.services.sandbox_runner import run_preflight_verification
from app.schemas.agent import PipelineResult, VerificationResult

app = FastAPI(title="Autonomous AI SRE Core Engine")

class TriageRequest(BaseModel):
    error_log: str
    source_code_context: str

class VerificationRequest(BaseModel):
    target_file: str
    remediated_code: str
    test_file_name: str
    generated_test_code: str

@app.get("/")
def read_root():
    return {"status": "online", "service": "Autonomous AI SRE Core Engine"}

@app.post("/api/triage", response_model=PipelineResult)
def triage_issue(request: TriageRequest):
    try:
        return run_sre_pipeline(request.error_log, request.source_code_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/verify", response_model=VerificationResult)
def verify_patch(request: VerificationRequest):
    try:
        return run_preflight_verification(
            target_file_rel_path=request.target_file,
            remediated_code=request.remediated_code,
            test_file_name=request.test_file_name,
            generated_test_code=request.generated_test_code,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))