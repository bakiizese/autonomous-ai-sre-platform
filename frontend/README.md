# 🖥️ Autonomous AI SRE — Frontend Dashboard

> The real-time interactive user interface for the Autonomous AI SRE Platform. Built with React, TypeScript, Vite, and Tailwind CSS, it provides real-time visualization of error ingestion, agent diagnostic reasoning, sandbox test verification, and automated GitHub PR dispatching.

---

## 🛠️ Tech Stack & Key Libraries

* **Framework:** React 18 (TypeScript)
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
│   │   │   └── Layout.tsx  # Navigation header, sidebar & page framing
│   │   └── PipelineRail.tsx # Visual execution pipeline tracker component
│   ├── pages/              # Primary view screens
│   │   ├── Home.tsx        # Platform landing & feature overview
│   │   ├── Dashboard.tsx   # Live agent control room, issue trigger & status logs
│   │   └── About.tsx       # System architecture & team details
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

Create a `.env` file in the `frontend/` directory (if targeting a custom API URL):

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 4. Running the Development Server

Start the Vite development server:

```bash
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## ⚙️ Key UI Features

* **Real-time Pipeline Rail:** Visual step-by-step indicator (`PipelineRail.tsx`) tracking issue ingestion, code resolution, Gemini diagnosis, sandbox verification, and PR creation.
* **Interactive Remediation Trigger:** Form inputs and dropdowns to dispatch GitHub issue remediation requests directly to the agent.
* **Telemetry & Console Logs:** Live output feed showing sandbox test results and generated code diffs.