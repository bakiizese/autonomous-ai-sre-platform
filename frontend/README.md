# 💻 Autonomous AI SRE — Developer Command Center UI

> The human-in-the-loop developer interface for the Autonomous AI SRE Platform. Built with React, Vite, and Tailwind CSS, it provides real-time metric tracking, side-by-side colorized git diffs, test verification proof badges, and 1-click GitHub PR approval controls.

---

## 🛠️ Tech Stack & Tools

* **Core Framework:** React 18 (Vite)
* **Styling:** Tailwind CSS
* **Icons:** Lucide React
* **Linting & Quality:** Oxlint & ESLint
* **HTTP Client:** Fetch API / Axios

---

## 📂 Submodule Architecture

```text
frontend/
├── src/
│   ├── components/    # Reusable UI widgets (DiffViewer, TestBadges, MetricCards)
│   ├── services/      # Backend API integration client
│   ├── App.jsx        # Main Dashboard layout & state orchestrator
│   ├── main.jsx       # React application entry point
│   └── index.css      # Tailwind directives & base styling
├── index.html         # HTML entry document
├── package.json       # Node dependencies & execution scripts
└── vite.config.js     # Vite configuration
