# 🛡️ Autonomous AI SRE & Code Remediation Platform

An end-to-end, human-governed AI Reliability Engineer powered by Gemini 2.5 Flash, FastAPI, and React. Auto-triages errors, executes isolated pre-flight verifications, and manages GitHub PR lifecycles.

---

## 🌟 Overview & System Features

* **🤖 Multi-Agent AI Engine:** Powered by Google Gemini 2.5 Flash to perform root-cause analysis, generate contextual fixes, and draft comprehensive unit tests.
* **🧪 Isolated Dual-Tier Sandboxing:** Pre-flight code verification using `pytest` inside temporary filesystem sandboxes before any code is committed.
* **🐙 GitHub Workflow Automation:** Automated branch creation, commit staging, and Pull Request generation with full trace logs.
* **📧 Critical Incident Alerts:** Automated transactional email dispatcher to notify lead engineers when high-severity bugs are remediated.
* **📊 Interactive Dashboard:** React + TypeScript control room providing visual execution pipeline rails (`PipelineRail`), telemetry feeds, and manual trigger controls.

---

## 🏗️ System Architecture

```text
┌────────────────┐     HTTP POST     ┌──────────────────────┐
│  React Frontend│ ────────────────▶ │  FastAPI Core Engine │
│  (Port 5173)   │ ◀──────────────── │  (Port 8000)         │
└────────────────┘   Telemetry/PR    └──────────┬───────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
    ┌────────────────────────┐    ┌────────────────────────┐    ┌────────────────────────┐
    │  Gemini 2.5 Flash SDK  │    │ Sandbox Runner (Pytest)│    │   GitHub REST API      │
    │  (Diagnosis & Patch)   │    │  (Pre-flight Verify)   │    │  (Branch & PR Dispatch)│
    └────────────────────────┘    └────────────────────────┘    └────────────────────────┘
```

---

## 📂 Repository Layout

```text
.
├── backend/          # FastAPI engine, Gemini multi-agent logic, sandbox execution, GitHub & email services
└── frontend/         # React 18 + Vite dashboard, Tailwind styling, and real-time execution tracking
```

---

## 🚀 Quick Start Guide

### Prerequisites
* Python 3.10+
* Node.js v18+ & npm
* Git & GitHub Personal Access Token (PAT)
* Google AI Studio API Key

### 1. Backend Setup

```bash
cd backend

# Create & activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (.env)
cp .env.example .env  # Add your GEMINI_API_KEY, GITHUB_TOKEN, and SMTP credentials

# Run FastAPI engine
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run Vite dev server
npm run dev
```

Visit `http://localhost:5173` to access the interactive SRE control panel!

---

## 📄 License & Attribution

Distributed under the MIT License. Built for autonomous systems engineering, reliability testing, and developer productivity workflows.