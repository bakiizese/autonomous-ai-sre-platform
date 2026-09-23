# 🖥️ Autonomous AI SRE — Frontend Dashboard

> The real-time interactive user interface for the Autonomous AI SRE Platform. Built with React, TypeScript, Vite, and Tailwind CSS, it provides real-time visualization of error ingestion, agent diagnostic reasoning, sandbox test verification, and automated GitHub PR dispatching.

---

## 🛠️ Tech Stack & Key Libraries

* **Framework:** React 19 (TypeScript)
* **Build Tool:** Vite
* **Styling:** Tailwind CSS & Custom CSS Tokens (`src/styles/tokens.css`)
* **Icons & UI:** Lucide React / Heroicons
* **API Client:** Axios / Fetch API wrapper (`src/services/api.ts`)
* **State & Types:** TypeScript interfaces (`src/types/agent.ts`)

---

## 📂 Directory Structure

```text
frontend/
├── index.html              # Entry HTML with custom SVG favicon & title
├── package.json            # Scripts & project dependencies
├── README.md               # Frontend documentation
├── src/
│   ├── App.tsx             # Root application component & routing setup
│   ├── main.tsx            # Application entry point & DOM mounting
│   ├── index.css           # Global Tailwind CSS imports & base styles
│   ├── assets/             # Static graphics & iconography
│   │   ├── hero.png
│   │   ├── react.svg
│   │   └── vite.svg
│   ├── components/         # Reusable UI components
│   │   ├── layout/
│   │   │   └── Layout.tsx  # Navigation header & page framing
│   │   ├── PipelineRail.tsx       # Visual execution pipeline tracker
│   │   ├── RateLimitBadge.tsx     # Live Gemini/GitHub rate-limit status (polls the backend)
│   │   ├── ApprovalModal.tsx      # Human-in-the-loop review of a proposed fix
│   │   ├── RunResultPanel.tsx     # Diagnosis, diff, test, and agent-graph trace for a run
│   │   ├── EmailSubscribeForm.tsx # Critical-risk email alert signup
│   │   └── VideoPlaceholder.tsx   # Walkthrough video embed / "coming soon" card
│   ├── lib/
│   │   └── runStatus.ts    # Run status display, risk colors, pipeline-rail mapping
│   ├── pages/              # Primary view screens
│   │   ├── Home.tsx        # Landing page: overview, walkthrough video, free-tier notice, V2 teaser
│   │   ├── Dashboard.tsx   # Repo selector, issue list, approval queue, sandbox demo, scratchpad
│   │   └── About.tsx       # System architecture & stack
│   ├── services/
│   │   └── api.ts          # Axios backend API client & endpoint definitions
│   ├── styles/
│   │   └── tokens.css      # Custom design tokens & theme variable overrides
│   └── types/
│       └── agent.ts        # TypeScript definitions for remediation tasks & telemetry
├── tsconfig.json           # TypeScript configuration
└── vite.config.ts          # Vite bundler & development proxy configuration
```

---

## 🚀 Getting Started

### 1. Prerequisites
* Node.js (v18 or higher)
* npm or yarn
* Running backend service at `http://localhost:8000`

### 2. Installation

Navigate to the `frontend` directory and install dependencies:

```bash
cd frontend
npm install
```

### 3. Environment Configuration

Create a `.env` file in the `frontend/` directory (both variables are optional):

```env
# Backend base URL (defaults to http://localhost:8000)
VITE_API_BASE_URL=http://localhost:8000

# Walkthrough video shown on the landing page — a YouTube/Loom/Vimeo embed URL
# or a direct video file URL. Leave unset to show the "coming soon" card.
VITE_WALKTHROUGH_VIDEO_URL=
```

### 4. Running the Development Server

Start the Vite development server:

```bash
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## ⚙️ Key UI Features

* **Multi-repo dashboard:** Pick a writable sandbox repo (full loop) or connect any public repo for read-only inspection. Existing open issues are ingested as a baseline and are only diagnosed on demand.
* **Human-in-the-loop approval:** Sandbox-repo fixes stop at an "awaiting approval" queue; the review modal shows the diff, generated test, and sandbox proof, and nothing is written to GitHub until you approve.
* **Inject a bug:** One click opens a real canned bug report on the sandbox repo and runs the whole loop on it.
* **Check now:** Ask the backend poller to check for new issues immediately instead of waiting for its 30s interval.
* **Rate-limit visibility:** Header badges show live Gemini and GitHub availability (the demo runs on free-tier keys).
* **Email alerts:** Enter an email to be notified right away when a diagnosis on the repo scores above 8/10.
* **Agent graph trace:** Each run shows which graph nodes executed, retries included, and how long each took.
* **Scratchpad:** Paste an error and source directly to run the agent graph without touching any repository.