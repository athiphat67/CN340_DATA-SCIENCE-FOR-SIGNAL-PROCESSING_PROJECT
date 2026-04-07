# Task List: Migrate Gradio Dashboard to React & FastAPI

- [x] Inspect existing dependencies (like `fastapi`, `uvicorn`, `cors`) and install if needed.
- [x] Create FastAPI Backend
  - [x] Initialize `Src/api/main.py` with FastAPI.
  - [x] Connect existing `services` (Analysis, History, Portfolio) to API routes.
  - [x] Implement endpoints: `/api/analysis`, `/api/history`, `/api/portfolio`.
  - [x] Implement CORS for the local frontend development.
- [/] Set up Vite + React + TypeScript Frontend
  - [x] Initialize Vite project in `Src/frontend/`.
  - [x] Install Tailwind CSS.
  - [x] Create basic dashboard layout.
  - [x] Implement Analysis Page fetching from `/api/analysis`.
  - [x] Implement History Page fetching from `/api/history`.
  - [x] Implement Portfolio Page fetching from `/api/portfolio`.
- [ ] Integrate & Test
  - [ ] Run both servers concurrently.
  - [ ] Verify functionality matches original Gradio app.
