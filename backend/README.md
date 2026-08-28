# ⚙️ Autonomous AI SRE — Backend Service

> The high-performance core engine for the Autonomous AI SRE Platform. Powered by FastAPI, Gemini 2.5 Flash, and Python's subprocess sandboxing, it handles error ingestion, multi-agent AI diagnosis, dual-tier test verification, and GitHub workflow execution.

---

## 🛠️ Tech Stack & Dependencies

* **Framework:** FastAPI (Python 3.10+)
* **Server:** Uvicorn
* **AI Provider:** Google AI Studio SDK (`google-genai`) using `gemini-2.5-flash`
* **Validation & Schemas:** Pydantic v2
* **Sandboxing & Verification:** Python `tempfile` & `subprocess` executing `pytest`
* **State Management:** SQLite / In-Memory State

---

## 📂 Submodule Architecture

```text
backend/
├── agent.py          # Gemini multi-agent orchestrator (Diagnosis, Remediation, Test Gen)
├── schemas.py        # Pydantic structured output models for LLM responses
├── main.py           # FastAPI REST API routing & orchestration endpoints
├── sandbox.py        # Isolated tempfile execution runner for dual-tier pytest checks
├── requirements.txt  # Core Python dependencies
└── .env              # Environment configuration & secret keys
