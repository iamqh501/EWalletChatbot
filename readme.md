# E-Wallet & Telecom AI Assistant

An asynchronous, two-stage agentic AI assistant for E-Wallet customer support, in-app screen navigation, personal transaction inquiry, and telecom package consultation. Built with FastAPI, Qdrant hybrid vector search, TypeSafe Jev reranking and history scoring, and a dual-interface React / Vite frontend.

## 1. Architecture Overview

```text
                                 [ User ]
                                    │
                  (1. Submits text query with optional image)
                                    │
               ┌────────────────────┴────────────────────┐
      [ Image Attached ]                          [ Text-Only Query ]
               │                                         │
               ▼                                         │
  [ VLM - Ling-3.0-flash-VL ]                            │
  (Structured VLMResponse: OCR, UI inspection,           │
   and query synthesis into rewritten_query)             │
               │                                         │
               └────────────────────┬────────────────────┘
                                    │
                                    ▼
             [ History Relevance Scorer - TypeSafe Jev ]
       (Scores up to 10 recent turns via Harmonic Bridge and
        includes turns with u_i >= 0.7 as conversation context)
                                    │
                                    ▼
┌─────────────────── [ LLM Stage 1: Tool Router ] ────────────────────┐
│          (Selects and invokes tools ONLY — never answers)           │
│                                                                     │
│   ├───> search_general_knowledge  (Policies, fees & FAQ qa.xlsx)    │
│   ├───> search_telecom_packages   (Telecom plan catalog filter)     │
│   ├───> guide_app_task            (Task guide & navigation_map)     │
│   ├───> get_transaction_history   (Transactions & consent check)    │
│   └───> resolve_intent            (3-step ambiguity resolution)     │
└───────────────────────────────────┼─────────────────────────────────┘
                                    │
               (Typed ToolResultItem blocks + History Context)
                                    │
                                    ▼
┌────────────── [ LLM Stage 2: Final Response Synthesis ] ────────────┐
│  (Mandatory for all turns; enforces strict grounding and formatting)│
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
        (Server-Sent Events: thinking, status, token, consent, stats)
                                    │
                                    ▼
                     [ User ] (Receives streamed response)
```

## 2. Two-Stage LLM Execution

Decoupling tool routing from final response generation avoids interference between JSON tool-argument extraction and strict Markdown output rules.

- Stage 1 (`TOOL_ROUTING_SYSTEM_PROMPT`): Analyzes the query and relevant history context exclusively to select tools (up to 1 call per tool per turn; supports concurrent multi-tool calls). It never answers the user directly, and all reasoning tokens are streamed to the `<think>` channel. Casual greetings or queries already answered by history context bypass tool calls and proceed directly to Stage 2.
- Stage 2 (`FINAL_RESPONSE_SYSTEM_PROMPT`): Mandatory for every turn. Synthesizes the user-facing response strictly from retrieved tool results and conversation history without fabrication or subjective commentary, while preserving Markdown tables and verbatim policy phrasing.

## 3. Agent Tools

All tools are created per turn in `backend/tools/factory.py` and return typed models defined in `backend/tools/schemas.py`.

1. `search_general_knowledge`: Runs concurrent dense (`google/embeddinggemma-300m`, 768-dim) and sparse (`Qdrant/bm25`) query embeddings, executes Qdrant RRF hybrid search on child chunks, resolves intact parent chunks from `parent_store/`, and reranks them with TypeSafe Jev ($\text{score} \ge 0.6$).
2. `search_telecom_packages`: Filters cached `TelecomPackage` records (`docs/telecom/goi_cuoc.json`) by package code, price range (VND), billing cycle in days (`7`, `30`, `360`), and daily data allowance (GB/day).
3. `guide_app_task`: Retrieves task instructions from `docs/navigation/cach_dung_app.md` via filtered hybrid search and supplies `docs/navigation/navigation_map.json` so Stage 2 can synthesize step-by-step screen navigation from the user's current screen.
4. `get_transaction_history`: Checks session-scoped privacy consent in `SessionManager`. If ungranted, emits a `consent_required` SSE event to display an interactive Allow/Deny card in the chat UI; if granted, returns personal transaction records.
5. `resolve_intent`: Evaluates ambiguous or underspecified queries using a 3-step prompt (Hypotheses, Evidence Evaluation, Decision) to select the best interpretation or ask a clarifying question.

## 4. Key Technical Design

- Dual Frontend (React 19 & Vite 8):
  - User Chatbot UI (port `3000`): SSE streaming interface with a collapsible `<think>` accordion, image attachment/paste with lightbox preview, interactive privacy consent card, GFM table/math rendering, and latency telemetry.
  - Admin Document Manager (port `3001`): Standalone dashboard for managing documents across `knowledge/`, `faq/`, `telecom/`, and `navigation/`, featuring drag-and-drop upload, Markdown editing, visual Excel editing (Q&A cards and multi-column tables), and live vector re-indexing.
- Knowledge Indexing & Storage:
  - FAQ spreadsheets (`docs/faq/qa.xlsx`) use row-level chunking where vectors are computed only on the Question column, while verbatim Answers are stored in metadata and `parent_store/`.
  - Long Markdown tables are split every 10 rows while preserving headers in each chunk.
  - `DocumentManager` coordinates in-process Qdrant and store updates with `asyncio.Lock` and `asyncio.to_thread`, and automatically converts `docs/telecom/goi_cuoc.xlsx` to `goi_cuoc.json` on update.
- History Scoring (Harmonic Bridge):
  - `SessionManager` retains only `user_query` and `agent_output` (excluding raw `tool_output`).
  - `HistoryScorer` evaluates up to 10 recent turns in parallel with TypeSafe Jev using positional distance and the Harmonic Bridge formula ($u_i = 0.5 \cdot d_i + 0.5 \cdot \text{avg}(2 d_i r_{ij} / (d_i + r_{ij}))$), injecting turns with $u_i \ge 0.7$ into the prompt context.

## 5. Getting Started

All commands below use Windows 11 Command Prompt (`cmd.exe`).

### Prerequisites
- Windows 11 (x64), Python 3.11+, Node.js 20+ (`npm`)
- API keys: `HF_API_KEY` (Hugging Face Router) and `TYPESAFE_API_KEY` (TypeSafe Jev)

### 1. Install Backend & Frontend Dependencies

```cmd
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt

cd frontend
call npm install
cd ..
```

### 2. Configure Environment Variables

```cmd
copy .env.example .env
```

Edit `.env` and set your API keys:

```ini
TYPESAFE_API_KEY=your_typesafe_api_key_here
HF_API_KEY=your_huggingface_api_key_here

BACKEND_PORT=8000
FRONTEND_PORT=3000
ADMIN_PORT=3001

HF_LLM_MODEL_NAME=inclusionAI/Ling-3.0-flash:fastest
HF_VLM_MODEL_NAME=inclusionAI/Ling-3.0-flash-VL:fastest
HF_EMBEDDING_MODEL=google/embeddinggemma-300m
RERANKER_MODEL=jev-latest
```

### 3. Initialize the Knowledge Base (First Run)

Run offline conversion and vector indexing before starting the server:

```cmd
.venv\Scripts\python.exe index_docs.py --mode convert
.venv\Scripts\python.exe index_docs.py --mode reset
```

### 4. Run the Application

Automated startup (launches Backend on `:8000`, User UI on `:3000`, and Admin UI on `:3001`):

```cmd
run_app.bat
```

Or start each service manually in separate `cmd.exe` terminals:

```cmd
.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev:user -- --host 127.0.0.1 --port 3000
cd frontend && npm run dev:admin -- --host 127.0.0.1 --port 3001
```

## 6. CLI Reference (`index_docs.py`)

Note: Stop the backend server before running `index_docs.py` due to embedded Qdrant's exclusive file lock on `local_qdrant/`, or use the Admin UI (`http://127.0.0.1:3001`) while the server is running.

```cmd
.venv\Scripts\python.exe index_docs.py --reset
.venv\Scripts\python.exe index_docs.py --update
.venv\Scripts\python.exe index_docs.py --convert [--excel <PATH>] [--json <PATH>]
```

| Mode | Description |
|---|---|
| `--reset` | Clears `local_qdrant/`, `parent_store/`, and `docs/file_state.json`, then re-indexes all Markdown and FAQ Excel files from scratch. |
| `--update` | Incrementally indexes added, modified, or deleted files by comparing MD5 hashes against `docs/file_state.json`. |
| `--convert` | Converts `docs/telecom/goi_cuoc.xlsx` into `docs/telecom/goi_cuoc.json`. |
