# Project and Run Guide

This guide maps the application source files and describes a Windows local run.
The architecture overview and original design material are in
[`project_documentation.pdf`](./project_documentation.pdf).

## Run locally on Windows

Use two PowerShell terminals from the project root.

### 1. Configure and start the backend

```powershell
Copy-Item backend\.env.example backend\.env
Set-Location backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Edit `backend\.env` and set `MANAGEMENT_EMAILS` to approved management email
addresses and `MANAGEMENT_SIGNUP_TOKEN` to a long, random secret. Share the
token out-of-band with pre-approved managers only. Both the allowlisted email
and token are required to create a Management account; never commit or expose
the token in frontend configuration. Leave `LLM_PROVIDER=mock` for a keyless
local run, then start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The API and interactive docs are at `http://localhost:8000` and
`http://localhost:8000/docs`.

### 2. Configure and start the frontend

In another terminal, from the project root:

```powershell
Copy-Item frontend\.env.example frontend\.env
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Create a Student or Faculty account. Management
accounts are assigned server-side when a new account is created with an email
in `MANAGEMENT_EMAILS` and a valid `MANAGEMENT_SIGNUP_TOKEN`; Management is
intentionally not a selectable public role. An already-existing account is
not silently promoted when the allowlist changes; an operator must provision
that role explicitly.

Faculty upload a syllabus, wait for its status to become `ready`, create a
course from it on **Courses**, and share the displayed join code. Students
enter that code on **Courses** to access the syllabus topics and their own
learning tools. For a containerized run, see the Docker steps in the root
[`README.md`](../README.md).

## File guide

### Backend

| File | Purpose |
|---|---|
| `backend/app/main.py` | Creates the FastAPI app, initializes tables, configures CORS, and mounts routers. |
| `backend/app/database.py` | Builds the SQLAlchemy engine/session and request-scoped database dependency. |
| `backend/app/models.py` | Relational models for users, materials, topics, quizzes, mastery, courses, enrollments, and learning activity. |
| `backend/app/schemas.py` | Pydantic request and response contracts for the API. |
| `backend/app/core/config.py` | Environment-backed settings, including the Management email allowlist and signup token. |
| `backend/app/core/security.py` | Password/JWT helpers, current-user checks, and course-aware topic access. |
| `backend/app/core/cache.py` | Redis-backed conversational session cache helpers. |
| `backend/app/core/__init__.py` | Core package marker. |
| `backend/app/routers/auth.py` | Account creation, login, and current-user endpoints. |
| `backend/app/routers/syllabus.py` | Upload, ingestion status, listing, and deletion of course documents. |
| `backend/app/routers/topics.py` | Lists topics available to the signed-in user. |
| `backend/app/routers/courses.py` | Faculty course creation/listing, student join-code enrollment, and course topic access. |
| `backend/app/routers/study_plan.py` | Generates and retrieves an individual study plan. |
| `backend/app/routers/quiz.py` | Quiz and diagnostic generation/submission, answer checks, and activity recording. |
| `backend/app/routers/study.py` | Generates study lessons and records study activity. |
| `backend/app/routers/study_kit.py` | Generates summaries, flashcards, guides, and practice quizzes. |
| `backend/app/routers/remediation.py` | Produces targeted learning modules after low quiz scores. |
| `backend/app/routers/chat.py` | REST/WebSocket tutor chat and chat history. |
| `backend/app/routers/progress.py` | Student mastery/activity summaries and Faculty per-course analytics. |
| `backend/app/routers/management.py` | Aggregated platform metrics restricted to Management accounts. |
| `backend/app/routers/__init__.py` | Router package marker. |
| `backend/app/agent/graph.py` | LangGraph tutor workflow and tool dispatch. |
| `backend/app/agent/router.py` | Classifies the user request and selects a tutor capability. |
| `backend/app/agent/state.py` | Shared state shape for the tutor graph. |
| `backend/app/agent/quiz_tools.py` | Quiz generation, grading, diagnostic assessment, and mastery updates. |
| `backend/app/agent/study_planner.py` | Orders topics and builds a mastery-aware study plan. |
| `backend/app/agent/content_generator.py` | Creates multi-part topic study kits. |
| `backend/app/agent/remediation.py` | Builds remediation lessons for weak concepts. |
| `backend/app/agent/__init__.py` | Agent package marker. |
| `backend/app/rag/ingestion.py` | Extracts and stores searchable content from uploaded documents. |
| `backend/app/rag/chunking.py` | Splits source content into retrieval-sized passages. |
| `backend/app/rag/topic_extraction.py` | Extracts course topics and hierarchy from uploaded material. |
| `backend/app/rag/query_engine.py` | Retrieves relevant passages for tutor responses. |
| `backend/app/rag/vector_store.py` | Persists, searches, and removes vector embeddings. |
| `backend/app/rag/__init__.py` | RAG package marker. |
| `backend/app/llm/base.py` | Provider-independent completion and embedding interface. |
| `backend/app/llm/factory.py` | Selects the configured LLM provider. |
| `backend/app/llm/local_embeddings.py` | Local embedding implementation. |
| `backend/app/llm/providers/mock_provider.py` | Deterministic keyless provider for development and tests. |
| `backend/app/llm/providers/grok.py` | xAI Grok provider adapter. |
| `backend/app/llm/providers/groq_provider.py` | Groq provider adapter. |
| `backend/app/llm/providers/openai_provider.py` | OpenAI provider adapter. |
| `backend/app/llm/providers/ollama_provider.py` | Local Ollama provider adapter. |
| `backend/app/llm/providers/__init__.py` | Provider package marker. |
| `backend/app/llm/__init__.py` | LLM package marker. |
| `backend/app/__init__.py` | Backend application package marker. |
| `backend/requirements.txt` | Python runtime dependencies. |
| `backend/Dockerfile` | Backend container build and startup instructions. |
| `backend/.env.example` | Local backend environment template. |
| `backend/.dockerignore` | Files excluded from the backend image build. |

### Frontend

| File | Purpose |
|---|---|
| `frontend/src/main.jsx` | Mounts React, routing, and the auth provider. |
| `frontend/src/App.jsx` | Declares application routes and role restrictions. |
| `frontend/src/index.css` | Global styles, theme tokens, and shared UI classes. |
| `frontend/src/context/AuthContext.jsx` | Loads and manages the signed-in user and auth token. |
| `frontend/src/lib/api.js` | Authenticated API client and endpoint functions. |
| `frontend/src/lib/speech.js` | Browser speech synthesis helpers for tutor mode. |
| `frontend/src/components/Nav.jsx` | Role-aware application navigation and sign-out. |
| `frontend/src/components/ProtectedRoute.jsx` | Authentication and role guard for routes. |
| `frontend/src/components/MasteryRing.jsx` | Reusable visual mastery indicator. |
| `frontend/src/pages/Dashboard.jsx` | Student learning dashboard, weekly metrics, recommendations, and recent activity. |
| `frontend/src/pages/FacultyDashboard.jsx` | Faculty course summaries, join codes, activity, and low-mastery topics. |
| `frontend/src/pages/ManagementDashboard.jsx` | Management platform-wide metric cards. |
| `frontend/src/pages/Courses.jsx` | Faculty course setup and student join-code/course-topic views. |
| `frontend/src/pages/Progress.jsx` | Student mastery details and Faculty per-course progress. |
| `frontend/src/pages/Upload.jsx` | Syllabus and course material upload/ingestion status. |
| `frontend/src/pages/DiagnosticQuiz.jsx` | Overall diagnostic quiz flow. |
| `frontend/src/pages/Quiz.jsx` | Topic quiz flow, results, and remediation prompt. |
| `frontend/src/pages/Study.jsx` | Lesson display and text-to-speech controls. |
| `frontend/src/pages/StudyKit.jsx` | Study kit display and remediation flow. |
| `frontend/src/pages/Chat.jsx` | Tutor chat interface and conversation history. |
| `frontend/src/pages/Login.jsx` | Sign-in form. |
| `frontend/src/pages/Signup.jsx` | Student/Faculty registration form and optional operator-issued Management token field. |
| `frontend/package.json` | Frontend scripts and direct dependencies. |
| `frontend/package-lock.json` | Locked frontend dependency tree. |
| `frontend/vite.config.js` | Vite and Tailwind build configuration. |
| `frontend/index.html` | Browser entry document and page metadata. |
| `frontend/public/tutor-mark.svg` | Public application icon. |
| `frontend/Dockerfile` | Frontend build and static-server container. |
| `frontend/nginx.conf` | Static server configuration and SPA route fallback. |
| `frontend/.env.example` | Frontend API base URL template. |
| `frontend/.dockerignore` | Files excluded from the frontend image build. |

### Root and documentation

| File | Purpose |
|---|---|
| `.env.example` | Docker Compose environment template. |
| `docker-compose.yml` | Starts PostgreSQL, Redis, backend, and frontend services. |
| `.gitignore` | Excludes local environments, secrets, and generated files from version control. |
| `README.md` | Project summary, stack, feature overview, and quick-start links. |
| `docs/sample_syllabus.json` | Example syllabus input for a local walkthrough. |
| `docs/project_documentation.pdf` | Original project architecture and requirements document. |

`backend/tutor.db` and `backend/test.db` are local SQLite data files, not
application source. `backend/data/` and `frontend/dist/` are generated runtime
or build output.
