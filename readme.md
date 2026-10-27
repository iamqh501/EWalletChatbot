# E-Wallet & Telecom AI Assistant

An asynchronous, two-stage agentic AI assistant built for **E-Wallet** customer support, in-app screen navigation, personal transaction inquiry, and telecommunications package consultation. The system combines multimodal Vision-Language preprocessing, Parent-Child Hybrid RAG (Qdrant + FastEmbed + Hugging Face Embeddings), TypeSafe Jev (`Noul`) semantic reranking and conversation history scoring, and a dual-interface React 19 / Vite 8 frontend.

---

## Table of Contents

1. [AI Agent Architecture (Two-Stage Execution Flow)](#1-ai-agent-architecture-two-stage-execution-flow)
2. [Two-Stage System Prompt Design](#2-two-stage-system-prompt-design)
3. [Agent Tool Suite](#3-agent-tool-suite)
4. [System Engineering & Technical Architecture](#4-system-engineering--technical-architecture)
5. [Getting Started (First-Time Setup & Execution)](#5-getting-started-first-time-setup--execution)
6. [Knowledge Base CLI Reference (`index_docs.py`)](#6-knowledge-base-cli-reference-index_docspy)

---

## 1. AI Agent Architecture (Two-Stage Execution Flow)

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
  (Structured output via VLMResponse:                    │
   OCR, UI/banner inspection, and                        │
   query synthesis into rewritten_query)                 │
               │                                         │
               └────────────────────┬────────────────────┘
                                    │
                                    ▼
             [ History Relevance Scorer - TypeSafe Jev ]
       (Evaluates up to 10 recent turns in parallel, computes u_i
        via Harmonic Bridge with positional awareness, and filters
        turns with u_i >= 0.7 into conversational context)
                                    │
                                    ▼
┌─────────────────── [ LLM Stage 1: Tool Router ] ────────────────────┐
│          (Selects and invokes tools ONLY — never answers)           │
│                                                                     │
│   ┌───> Tool 1: [ search_general_knowledge ] ───────────────────┐   │
│   │        └─ (Policies, fee schedules & FAQ qa.xlsx)           │   │
│   │                                                             │   │
│   ├───> Tool 2: [ search_telecom_packages ] ────────────────────┤   │
│   │        └─ (Telecom data/voice plan catalog filter)          │   │
│   │                                                             │   │
│   ├───> Tool 3: [ guide_app_task ] ─────────────────────────────┤   │
│   │        └─ (Task guide retrieval & navigation_map grounding) │   │
│   │                                                             │   │
│   ├───> Tool 4: [ get_transaction_history ] ────────────────────┤   │
│   │        └─ (Personal transaction lookup & consent check)     │   │
│   │                 │ (If consent is not yet granted)           │   │
│   │                 ▼                                           │   │
│   │            [ consent_required -> UI Consent Action Card ]   │   │
│   │                                                             │   │
│   └───> Tool 5: [ resolve_intent ] ─────────────────────────────┤   │
│            └─ (3-step structured ambiguity resolution)          │   │
└───────────────────────────────────┼─────────────────────────────┴───┘
                                    │
               (Typed ToolResultItem blocks + History Context)
                                    │
                                    ▼
┌────────────── [ LLM Stage 2: Final Response Synthesis ] ────────────┐
│       (MANDATORY for 100% of turns under strict formatting rules)   │
│  - Synthesizes greetings, history-based answers, or tool results    │
│  - Presents privacy consent prompts or personal transaction tables  │
│  - Zero hallucination, no subjective commentary, preserves tables   │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
        (Server-Sent Events: thinking, status, token, consent, stats)
                                    │
                                    ▼
                     [ User ] (Receives streamed response)
```

---

## 2. Two-Stage System Prompt Design

Decoupling tool routing from final response generation prevents instruction interference between JSON tool-argument extraction and strict Markdown output formatting constraints.

### Stage 1: Tool Routing (`TOOL_ROUTING_SYSTEM_PROMPT`)
- **Single Responsibility (Tool Selection Only)**: Stage 1 analyzes the user's query (or VLM `rewritten_query`) alongside relevant history context to decide which tools to invoke. **It never answers the user directly.** Any reasoning tokens or intermediate thoughts emitted during Stage 1 are routed exclusively into the `<think>` SSE channel.
- **Concurrent Multi-Tool Invocation**: When a user request spans multiple domains (e.g., asking for a data package recommendation and how to purchase it on the app), Stage 1 can invoke multiple tools within the same turn.
- **Per-Turn Invocation Cap**: Each tool is restricted to at most **1 execution per query turn** via `AgentToolContext.limits`.
- **Zero-Tool Bypass Conditions**:
  - Casual conversational greetings or closings (`hello`, `xin chào`, `cảm ơn`, `tạm biệt`).
  - Queries whose answer is already completely satisfied by `[NGỮ CẢNH TỪ LỊCH SỬ TRÒ CHUYỆN LIÊN QUAN]` (historical turns scoring $u_i \ge 0.7$).
  In these cases, Stage 1 terminates without calling any tool and hands control directly to Stage 2.
- **Mandatory Domain Routing Rules**:
  - `get_transaction_history`: Invoked when the user asks to view personal transaction records (transfers, receipts, bill payments, top-ups) or responds to a privacy consent prompt (`đồng ý`, `cho phép`, `không đồng ý`).
  - `guide_app_task`: Invoked when the user asks for step-by-step UI navigation or tap instructions inside the E-Wallet app (e.g., how to top up a phone, buy 4G/5G data, or navigate to the History tab). Never used for fetching actual personal transaction records.
  - `search_telecom_packages`: Invoked for mobile data and voice plan queries (plan code, price, cycle length, daily data allowance).
  - `search_general_knowledge`: Invoked for e-wallet policies, service fees, terms and conditions, bank linking, and general FAQ items.
  - `resolve_intent`: Invoked when the query is underspecified, ambiguous, or missing critical entity references.

### Stage 2: Final Response Synthesis (`FINAL_RESPONSE_SYSTEM_PROMPT`)
- **100% Mandatory Execution**: Stage 2 runs on **every turn**—whether responding to a casual greeting, answering from conversation history, requesting privacy consent, or synthesizing multi-tool outputs—guaranteeing a uniform persona and formatting standard.
- **Strict Grounding & Factual Integrity**:
  - Synthesizes answers strictly from `[DỮ LIỆU ĐÃ TRA CỨU ĐƯỢC TỪ HỆ THỐNG VÀ LỊCH SỬ]`. Never fabricates policies, fees, or package attributes.
  - **Greetings**: Responds concisely and politely as the E-Wallet virtual assistant.
  - **History-Based Answers**: Remains consistent with previously established conversation facts.
  - **Ambiguity Resolution (`resolve_intent`)**: Clearly presents the most probable interpretations or asks a concise clarifying question.
  - **Missing Information**: Explicitly states that no matching documentation was found rather than guessing.
  - **Privacy Consent (`consent_required`)**: Politely explains that viewing personal transaction history requires authorization and invites the user to click **Allow** (`Cho phép`) or **Deny** (`Không cho phép`) on the interactive chat card.
  - **Personal Transaction Records**: Formats transaction details faithfully (timestamp, transaction type, amount, counterparty, description).
- **Zero Commentary & Verbatim Fidelity**: Avoids filler, subjective advice, or unnecessary paraphrasing that could alter policy meanings. Preserves Markdown tables and structured lists intact.

---

## 3. Agent Tool Suite

All tools are dynamically instantiated per request via `create_agent_tools(context: AgentToolContext)` in `backend/tools/factory.py` and populate strongly typed `ToolResultItem` records defined in `backend/tools/schemas.py`.

### 1. `search_general_knowledge`
- **Purpose**: Retrieves e-wallet policies, fee schedules, terms of service, and FAQ entries (`docs/faq/qa.xlsx`).
- **Arguments (`SearchGeneralKnowledgeArgs`)**:
  - `query` (`str`): Search query or keywords.
- **Execution Mechanism**:
  - Computes Dense (`google/embeddinggemma-300m`, 768-dim) and Sparse (`Qdrant/bm25` via FastEmbed) query vectors concurrently.
  - Executes Qdrant Hybrid Search with Reciprocal Rank Fusion (RRF) over child chunks.
  - Deduplicates parent document IDs and fetches intact parent chunks from `parent_store/`.
  - Reranks parent documents via TypeSafe Jev (`NoulCriteria`) and filters results with $\text{score} \ge 0.6$.
- **Limit**: 1 call / turn.
- **Output**: Typed `KnowledgeChunk` list with source filenames, relevance scores, and parent chunk content.

### 2. `search_telecom_packages`
- **Purpose**: Searches and filters mobile data and voice telecom packages based on structured criteria.
- **Arguments (`SearchTelecomPackagesArgs`)**:
  - `package_name` (`Optional[str]`): Package code or substring (e.g., `YOLO90_12T`, `BIG`, `D169G`).
  - `price_min` / `price_max` (`Optional[float]`): Price range in VND.
  - `cycle_days_min` / `cycle_days_max` (`Optional[int]`): Billing cycle in days (standardized: 1 week = 7 days, 1 month = 30 days, 1 year = 360 days).
  - `data_gb_per_day_min` / `data_gb_per_day_max` (`Optional[float]`): Daily high-speed data allowance range in GB/day.
- **Execution Mechanism**: Filters in-memory cached `TelecomPackage` models loaded from `docs/telecom/goi_cuoc.json` (automatically synchronized whenever `docs/telecom/goi_cuoc.xlsx` is updated), sorting matches by cycle proximity and ascending price.
- **Limit**: 1 call / turn.
- **Output**: JSON-formatted list of matching packages (`Package Name`, `Price (VND)`, `Cycle (days)`, `Data per day (GB)`).

### 3. `guide_app_task`
- **Purpose**: Provides step-by-step UI operation instructions and screen navigation paths inside the E-Wallet app.
- **Arguments (`GuideAppTaskArgs`)**:
  - `task_query` (`str`): Description of the task the user wants to perform.
  - `current_screen` (`Optional[str]`): Name or ID of the screen the user is currently viewing (defaults to `HOME` if unspecified).
- **Execution Mechanism**:
  - Loads the cached screen transition topology from `docs/navigation/navigation_map.json` (`app_state.nav_map`).
  - Performs filtered Hybrid Search + Jev Reranking over `docs/navigation/cach_dung_app.md` to retrieve the matching task guide chunk and its `required_screen_id` metadata.
  - Supplies the task instructions, `current_screen`, `required_screen_id`, and `navigation_map.json` schema as grounding context so Stage 2 LLM can resolve the user's starting screen and synthesize a natural step-by-step navigation path.
- **Limit**: 1 call / turn.
- **Output**: Structured grounding block combining the retrieved task guide and screen transition map.

### 4. `get_transaction_history`
- **Purpose**: Retrieves the user's personal balance fluctuations and recent transaction history.
- **Arguments (`GetTransactionHistoryArgs`)**:
  - `query` (`Optional[str]`): Transaction category or filter keyword (e.g., transfers, receipts, recent).
  - `user_consent` (`Optional[bool]`): Explicit consent state (`True` if granted, `False` if denied, `None` on initial inquiry).
- **Privacy Consent Flow**:
  - Checks and updates session-scoped consent in `SessionManager` (`session_id`).
  - If consent has not been granted (`False` or `None`), sets `context.transaction_history_consent = True`, triggering the `consent_required` SSE event so the frontend renders an interactive Consent Action Card.
  - If consent is granted (`True`), returns a typed `TransactionHistoryResult` containing `TransactionRecord` items.
- **Limit**: 1 call / turn.
- **Output**: `TransactionHistoryResult` (`status`, `message`, `transactions`).

### 5. `resolve_intent`
- **Purpose**: Disambiguates vague, multi-meaning, or context-incomplete user queries.
- **Arguments (`ResolveIntentArgs`)**:
  - `query` (`str`): The user's ambiguous query.
  - `uncertainty_reason` (`str`): Specific reason why the intent is uncertain.
- **Execution Mechanism**: Invokes an auxiliary LLM call using `INTENT_RESOLVER_PROMPT` following a structured 3-step framework:
  1. **Hypotheses**: Enumerates plausible literal and contextual interpretations.
  2. **Evidence-Based Evaluation**: Weighs each hypothesis against conversation history, user query phrasing, and domain logic.
  3. **Decision**: Selects the highest-confidence interpretation, summarizes valid options, or formulates a brief clarifying question.
- **Limit**: 1 call / turn.
- **Output**: 3-step analytical breakdown passed to Stage 2 LLM.

---

## 4. System Engineering & Technical Architecture

### 1. Dual Frontend Architecture (React 19 & Vite 8)
- **User Chatbot Interface (Port `3000`)**:
  - Real-time SSE streaming client displaying terminal-style component initialization (`Knowledge Base`, `Dense Embedding`, `Sparse Embedding`, `Reranker`, `LLM`).
  - Collapsible `<think>` reasoning accordion that cleanly separates internal agent thoughts and VLM analysis from the final response.
  - Multimodal image attachment via file picker or direct clipboard paste (`Ctrl+V`), with thumbnail preview and an in-app **Lightbox modal** for inspecting attached images at full resolution.
  - Interactive **Consent Action Card** (`Allow` / `Deny`) that updates session privacy permissions via `/api/consent` and automatically triggers follow-up transaction retrieval.
  - GitHub Flavored Markdown tables (`remark-gfm`), LaTeX math rendering (`remark-math` + `rehype-katex`), custom `<br>` line-break rendering, and live telemetry metrics (TTFT, prompt/generation throughput in tokens/s, tool latency).
- **Admin Document Management Dashboard (Port `3001`)**:
  - Standalone full-page administration portal with isolated Vite dependency cache (`node_modules/.vite_admin`).
  - Live category tabs (`All`, `knowledge`, `faq`, `telecom`, `navigation`) with document counters and instant search filtering.
  - Drag-and-drop file upload with automatic or manual category routing and immediate vector indexing.
  - Full-screen Markdown text editor and a dual-mode visual Excel editor supporting both **Q&A card editing** (`docs/faq/qa.xlsx`) and **multi-column table editing** (`docs/telecom/goi_cuoc.xlsx`).
  - One-click incremental folder synchronization (`/api/docs/sync`) and per-file re-indexing (`/api/docs/{file_path}/reindex`).

### 2. LLM, VLM & Inference Hosting
- **Primary LLM**: Configurable via `HF_LLM_MODEL_NAME` (default: `inclusionAI/Ling-3.0-flash:fastest`).
- **Vision-Language Model (VLM)**: Configurable via `HF_VLM_MODEL_NAME` (default: `inclusionAI/Ling-3.0-flash-VL:fastest`).
  - Uses LangChain `with_structured_output(VLMResponse)` to stream progressive token deltas (`description` and `rewritten_query`) into the UI thinking block while guaranteeing schema-validated extraction without brittle regular expressions.
- **Inference Provider**: Hugging Face Router API (`https://router.huggingface.co/v1`) via `ChatDeepSeek` with native reasoning stream support and `stream_usage=True`.

### 3. Multi-Category Knowledge Base & In-Process `DocumentManager`
- **Categorized Directory Layout (`docs/`)**:
  - `docs/knowledge/`: Markdown documents covering e-wallet policies, fees, and service terms.
  - `docs/faq/`: Excel Q&A spreadsheet (`qa.xlsx`).
  - `docs/telecom/`: Telecom package catalog (`goi_cuoc.json`), source spreadsheet (`goi_cuoc.xlsx`), and supplementary Markdown notes (`goi_cuoc_data.md`).
  - `docs/navigation/`: App screen transition schema (`navigation_map.json`) and task guide (`cach_dung_app.md`).
  - `docs/file_state.json`: Tracks MD5 hashes, parent `doc_ids`, and Qdrant `point_ids` for incremental sync.
- **Row-Level Question-Only Embedding for FAQ Spreadsheets**:
  - Each row in `docs/faq/qa.xlsx` is indexed as an independent chunk.
  - Dense and sparse vectors are generated **exclusively from the Question column** (plus optional keywords), while the verbatim Answer is stored in payload metadata and `parent_store/`. This prevents long answer texts from diluting question similarity scores.
- **Header-Preserving Markdown Table Splitting**:
  - Markdown tables exceeding 10 rows are automatically split into 10-row chunks while repeating the original table header and separator lines in every chunk.
- **Non-Blocking In-Process Indexing & Cache Invalidation**:
  - `DocumentManager` shares the FastAPI server's live `app_state.qdrant_client` and `app_state.store` guarded by an `asyncio.Lock` to prevent embedded Qdrant file-lock conflicts.
  - Heavy disk I/O and embedding operations are offloaded via `asyncio.to_thread`.
  - Saving or uploading `docs/telecom/goi_cuoc.xlsx` automatically regenerates `docs/telecom/goi_cuoc.json` (`convert_telecom_excel_to_json`) and reloads `app_state.telecom_packages` and `app_state.nav_map`.

### 4. Hybrid Retrieval & Parent-Child Reranking
- **Concurrent Query Embedding**: Parallel execution of 768-dimensional Dense embeddings (`google/embeddinggemma-300m`) and BM25 Sparse embeddings (`Qdrant/bm25`).
- **Hybrid Fusion**: Qdrant `Prefetch` + Reciprocal Rank Fusion (`Fusion.RRF`) over child chunks.
- **Parent-Child Resolution & Jev Reranking**: Child hits are mapped to unique parent documents in `parent_store/` and scored in parallel by TypeSafe Jev (`jev-latest`, threshold $\ge 0.6$, context safety cap of 60,000 characters).

### 5. History Relevance Scoring & Harmonic Bridge
- **Memory-Efficient Turn Storage**: `SessionManager` stores up to 10 recent `ConversationTurn` objects containing only `user_query` and `agent_output`. Raw `tool_output` is excluded from session memory to prevent token bloat and cross-turn data contamination.
- **Positional Awareness & Harmonic Bridge**:
  - `HistoryScorer` evaluates recent turns in parallel with TypeSafe Jev, passing each turn's relative distance (`{diff} messages before current query`).
  - Computes direct relevance $d_i$ and bridges it with historical pairwise relevance $r_{ij}$:
    $$d_{\text{bridge}, ij} = \frac{2 \cdot d_i \cdot r_{ij}}{d_i + r_{ij}}, \qquad u_i = a \cdot d_i + (1 - a) \cdot \text{avg}_{j \neq i}\left(d_{\text{bridge}, ij}\right) \quad (a = 0.5)$$
  - Updates the symmetric matrix $r_{ij}$ each turn and injects turns with $u_i \ge 0.7$ into Stage 1 and Stage 2 prompts.

---

## 5. Getting Started (First-Time Setup & Execution)

All commands below are designed for **Windows 11 Command Prompt (`cmd.exe`)**.

### Prerequisites
- **OS**: Windows 11 (x64)
- **Python**: Python 3.11+ (tested with Python 3.14.8)
- **Node.js**: Node.js 20+ and `npm` (tested with Node.js v24.14.0)
- **API Keys**:
  - `HF_API_KEY`: Hugging Face API token with inference router permissions.
  - `TYPESAFE_API_KEY`: TypeSafe API key for Jev reranking and history scoring.

### Step 1: Create the Python Virtual Environment & Install Backend Dependencies

Open **Command Prompt (`cmd.exe`)** at the project root directory:

```cmd
python -m venv .venv
call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Install Frontend Dependencies

```cmd
cd frontend
call npm install
cd ..
```

### Step 3: Configure Environment Variables

Copy the template `.env.example` to `.env` in the project root:

```cmd
copy .env.example .env
```

Open `.env` and configure your API keys and desired ports/models:

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

### Step 4: Initialize the Knowledge Base (Required on First Run)

Before starting the backend server for the first time, convert the telecom spreadsheet into JSON and build the local Qdrant vector database (`local_qdrant/`) and parent document store (`parent_store/`):

```cmd
.venv\Scripts\python.exe index_docs.py --mode convert
.venv\Scripts\python.exe index_docs.py --mode reset
```

> **Note**: Local Qdrant uses an exclusive file lock on `local_qdrant/`. Run `index_docs.py` **before** launching the FastAPI server, or manage/sync documents directly from the Admin UI (`http://127.0.0.1:3001`) while the server is running.

### Step 5: Launch the Application

#### Option A: One-Click Automated Startup (Recommended)
Run the batch launcher from Command Prompt or Explorer:

```cmd
run_app.bat
```

`run_app.bat` automatically reads ports from `.env`, writes `frontend\.env`, cleans up stale listeners on ports `8000`, `3000`, and `3001`, and launches all three services in the background:
- **Backend API**: `http://127.0.0.1:8000` (Swagger docs at `http://127.0.0.1:8000/docs`)
- **User Chatbot UI**: `http://127.0.0.1:3000`
- **Admin Document Manager**: `http://127.0.0.1:3001`

Press any key inside the `run_app.bat` console window to gracefully stop all services.

#### Option B: Manual Startup in Separate `cmd.exe` Terminals

1. **Terminal 1 — Backend API**:
   ```cmd
   .venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000
   ```
2. **Terminal 2 — User Chatbot Frontend**:
   ```cmd
   cd frontend && npm run dev:user -- --host 127.0.0.1 --port 3000
   ```
3. **Terminal 3 — Admin Document Manager Frontend**:
   ```cmd
   cd frontend && npm run dev:admin -- --host 127.0.0.1 --port 3001
   ```

---

## 6. Knowledge Base CLI Reference (`index_docs.py`)

`index_docs.py` is a standalone CLI utility for offline vector indexing and telecom data conversion across `docs/knowledge/`, `docs/faq/`, `docs/telecom/`, and `docs/navigation/`.

### Syntax

```cmd
.venv\Scripts\python.exe index_docs.py --mode <reset|update|convert> [OPTIONS]
```

Or using shorthand flags:

```cmd
.venv\Scripts\python.exe index_docs.py --reset
.venv\Scripts\python.exe index_docs.py --update
.venv\Scripts\python.exe index_docs.py --convert [--excel <PATH>] [--json <PATH>]
```

### Modes

| Mode | Shorthand | Description |
|---|---|---|
| `reset` | `--reset` | Deletes `local_qdrant/`, `parent_store/`, and `docs/file_state.json`, then re-indexes all eligible Markdown (`docs/knowledge/*.md`, `docs/navigation/*.md`) and FAQ Excel (`docs/faq/*.xlsx`) files from scratch. |
| `update` | `--update` | Incrementally syncs added, modified, and deleted files by comparing MD5 checksums against `docs/file_state.json`. Falls back to `reset` if no prior database exists. |
| `convert` | `--convert` | Converts the telecom package spreadsheet (`docs/telecom/goi_cuoc.xlsx`) into structured JSON (`docs/telecom/goi_cuoc.json`). |
