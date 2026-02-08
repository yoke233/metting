# Meeting System MVP

This repository contains an MVP implementation for a multi-role architecture review meeting system.

## Features
- Multi-round meeting orchestration
- Shared context (MVP)
- Event stream (append-only)
- Pause/Resume
- ADR/Tasks/Risks artifacts
- CLI + REST API

## Quick start

### 1) Install dependencies

```powershell
uv venv
uv pip install -e .
```

### 1.5) Frontend dependencies (web UI)

```powershell
cd .\web
pnpm install
```

### 2) Run a meeting via CLI

```powershell
uv run python .\meeting\cli\run_meeting.py run --config .\examples\meeting_arch_review.json
```

### 3) Start the REST API

```powershell
uv run python -m uvicorn meeting.api.server:create_app --factory --reload
```

### 4) Start the frontend (Vite)

```powershell
cd .\web
pnpm dev
```

The UI runs at `http://127.0.0.1:5173` and proxies API calls to `http://127.0.0.1:8000`.

### 5) Sample REST flow

```powershell
# create meeting
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/meetings -Body (@{
  title = "Architecture Review"
  topic = "Review platform design"
  background = "Need 10k QPS"
  constraints = @{}
  roles = @("Chief Architect","Infra Architect","Security Architect","Skeptic","Recorder")
} | ConvertTo-Json) -ContentType "application/json"
```

## Storage
SQLite file defaults to `meeting.db` in the current directory.

## Notes
- Default runner uses LangChain (ChatOpenAI). Set `MEETING_RUNNER=stub` to use the stub runner.
- OpenAI auth options (OpenAI-compatible endpoints supported):
  - Set `OPENAI_API_KEY`.
  - Optional: set `OPENAI_BASE_URL` for a custom OpenAI-compatible endpoint.
  - Optional: set `OPENAI_CHAT_MODEL_ID` (default: `gpt-4o-mini`).
  - `.env` is auto-loaded if present.
- Role prompts are loaded from `config/settings.toml` via Dynaconf.
- System prompt is loaded from `config/settings.toml` via Dynaconf.
- Recorder output prompt is loaded from `config/settings.toml` (`recorder_output_prompt`).
- Completed runs save a `FLOWCHART` artifact (Mermaid) for the meeting flow.
- You can override in `config/.secrets.toml` (ignored by git).
- Frontend: supports Console view + Stage view (SSE streaming).
