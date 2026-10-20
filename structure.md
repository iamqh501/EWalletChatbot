# Project Structure

## Overview
E-Wallet and Telecom Assistant is a full-stack AI chatbot designed for e-wallet navigation and telecommunications package consultation. It features a FastAPI asynchronous streaming backend integrated with Qdrant vector search and a React/Vite single-page web UI.

## Runtime Environment
- Operating System: Windows 11 X64
- Backend Runtime: Python 3.14.8 (virtual environment at .venv)
- Frontend Runtime: Node.js v24.14.0, npm 11.9.0
- Command Shell: Windows Command Prompt (cmd.exe)
- Hardware Strategy: CPU execution mode (GPU NVIDIA RTX 3050 Ti disabled via CUDA_VISIBLE_DEVICES=-1 for stability)

## Directory and File Structure
- backend: FastAPI application, AI orchestration, retrieval services, tools, and endpoints
  - api: HTTP and SSE endpoints, request/response Pydantic models
    - routes.py: Endpoints for /api/query, /api/init-stream, /api/health
    - schemas.py: QueryRequest and HealthResponse data models
  - core: Application lifecycle, state management, and environment loaders
    - config.py: Paths, model constants, and directory definitions
    - env.py: Environment loader syncing .env and Windows Registry (HKCU\Environment)
    - state.py: AppState, background model loader, and SessionManager
  - prompts: System prompt definitions
    - routing.py: TOOL_ROUTING_SYSTEM_PROMPT for Call 1 tool selection
    - final_response.py: FINAL_RESPONSE_SYSTEM_PROMPT for Call 2 response synthesis
    - intent_resolver.py: Intent resolution 3-step prompt template
  - services: Core backend business logic
    - agent_orchestrator.py: Two-stage execution coordinator, stream handler, and tool caller
    - history_scorer.py: Session turn relevance evaluation using TypeSafe Jev
    - llm.py: LangChain ChatDeepSeek initialization with Hugging Face Router
    - retrieval.py: Hybrid search (dense and sparse) and Parent-Child Jev reranking
  - tools: Executable agent tools
    - factory.py: AgentToolContext and LangChain tool factory functions (create_agent_tools)
    - general_knowledge.py: Qdrant retrieval and parent document fetcher
    - telecom_packages.py: Telecom package catalog filter and search engine
    - intent_resolver.py: Structured 3-step reasoning resolver
    - schemas.py: Pydantic tool argument schemas
  - utils: Operational helpers
    - metrics.py: StreamMetricsTracker microsecond latency and token throughput recorder
    - stream_utils.py: Server-Sent Events (SSE) data formatting helpers
  - main.py: Application composition root, CORS setup, and router mounting
- frontend: Single-page application built with React and Vite
  - src: UI source code
    - App.jsx: Main chat interface, SSE stream parser, thinking accordion, and input controls
    - main.jsx: React root component bootstrap
    - App.css: Chat component styling and markdown table alignment
    - index.css: Global reset and base typography
  - index.html: HTML host document
  - vite.config.js: Vite build configuration
  - package.json: Node dependencies and build scripts
- docs: Knowledge base documents and telecom package data
  - goi_cuoc.json: Active telecom data plans catalog
  - goi_cuoc.xlsx: Source spreadsheet for data plans
  - 19 Markdown documents covering e-wallet policies, fees, and instructions
- local_qdrant: Persistent on-disk vector database directory
- parent_store: LocalFileStore directory holding intact parent document chunks
- index_docs.py: CLI utility for resetting, updating, and converting document collections
- run_app.bat: Windows batch launcher managing backend and frontend processes concurrently
- requirements.txt: Python backend package requirements
- mistake.md: Technical troubleshooting log and implementation caveats
- structure.md: Current system architecture and state documentation

## Core Architecture and Execution Flow
- Two-Stage LLM Call Architecture:
  - Call 1 (Routing and Tool Execution): Executes agent.astream with TOOL_ROUTING_SYSTEM_PROMPT. Analyzes query and conversation history to select either search_general_knowledge, search_telecom_packages, or resolve_intent. Streams internal reasoning (<think>) and tool invocation logs. If query is casual conversation, answers directly without Call 2.
  - Call 2 (Final Response Synthesis): Triggers when search context exists. Calls llm.astream with FINAL_RESPONSE_SYSTEM_PROMPT and retrieved documents. Produces strictly factual, unopinionated answers preserving original tables and lists without conversational filler.

## Retrieval and Knowledge Base Pipeline
- Parent-Child Retrieval Architecture:
  - Splits documents into small child chunks for vector matching and large intact parent chunks for LLM context.
  - Vector search identifies child chunk matches in Qdrant, deduplicates parent document IDs, and fetches full parent documents from parent_store.
- Hybrid Search:
  - Dense Embedding: 768-dimensional vectors generated via Hugging Face API using google/embeddinggemma-300m.
  - Sparse Embedding: BM25 sparse vectors generated via FastEmbed using Qdrant/bm25.
  - Fusion: Reciprocal Rank Fusion (RRF) merges dense and sparse scores.
- Reranking:
  - TypeSafe Jev model (Noul / jev-latest) reranks fetched parent documents against the query.
  - Filters out documents below score threshold 0.6. Context length limit safely capped at 60,000 characters.

## History Relevance Scoring and Context Engine
- Conversation Turn Modeling: Each turn stores user_query, agent_output, tool_output, and turn ID.
- Semantic Scoring: HistoryScorer evaluates up to 10 recent messages in parallel using TypeSafe Jev (Noul), prioritizing proximity when queries reference earlier context.
- Harmonic Bridge Algorithm:
  - d_bridge_ij = (2 x d_i x r_ij) / (d_i + r_ij)
  - u_i = 0.5 x d_i + 0.5 x avg(d_bridge_ij) for all j != i
  - Updated u_i is recorded into symmetric matrix r_ij for subsequent turns.
- Context Filtering: Turns with u_i >= 0.7 are included as valid context in Call 1, allowing the model to answer direct follow-up questions without redundant tool calls.

## Intent Resolution and Tool Suite
- Tool Factory Architecture: create_agent_tools dynamically instantiates LangChain tool instances with an AgentToolContext, enforcing per-turn invocation limits, collecting retrieved context for Call 2 synthesis, and recording structured thinking logs without embedding tool closures inside the orchestrator.
- search_general_knowledge: Executes hybrid search and Jev reranking against Qdrant and parent_store for e-wallet policies, fees, and instructions.
- search_telecom_packages: Queries docs/goi_cuoc.json by package name (partial matching), price range (VND), cycle days (e.g. 7, 30, 360), and daily data limits (GB/day).
- resolve_intent: Evaluates ambiguous or underspecified queries through a 3-step reasoning framework:
  1. Hypotheses: Enumerates literal and context-based interpretations.
  2. Evidence Evaluation: Cross-references query, conversation history, and task logic.
  3. Decision: Chooses optimal path, summarizes multiple interpretations, or proposes a concise clarifying question.

## API Endpoints and Telemetry
- POST /api/query: Accepts session ID and user query, returns Server-Sent Events stream of thinking tokens, tool logs, answer tokens, and performance metrics.
- GET /api/init-stream: Emits real-time loading events for Knowledge Base, Dense Embedding, Sparse Embedding, Reranker, and LLM until system readiness.
- GET /api/health: Returns JSON status with boolean is_ready flag and list of loaded components.
- StreamMetricsTracker: Measures TTFT (Time To First Token), prompt processing throughput (tokens/second), generation throughput (tokens/second), tool latency, and total query duration.

## Frontend UI and Markdown Rendering
- Built with React 19 and Vite 8 with auto-scroll and input pre-fill while models are warming up.
- Minimalist terminal-style monospace initialization banner (<Component>: loaded).
- Accordion thinking block to isolate reasoning traces from answer text.
- Markdown table formatting using remark-gfm with top-aligned cells.
- Custom component renderer converting embedded raw br HTML line breaks into JSX br elements.

## Document Indexing and Conversion CLI (index_docs.py)
- CLI Arguments:
  - --mode reset: Rebuilds Qdrant collection (768 dimensions), re-embeds all markdown documents in batches of 32, populates parent_store, and writes file_state.json.
  - --mode update: Compares current file MD5 hashes with file_state.json to incrementally add, update, or delete modified documents.
  - --mode convert: Converts spreadsheet docs/goi_cuoc.xlsx into formatted JSON docs/goi_cuoc.json.

## Libraries and Framework Versions
- Backend (Python 3.14.8):
  - fastapi: 0.142.1
  - uvicorn: 0.54.0
  - langchain: 1.4.3
  - langchain-core: 1.2.18
  - langchain-deepseek: 1.0.1
  - langchain-classic: 1.0.1
  - qdrant-client: 1.19.1
  - transformers: 5.17.0
  - torch: 2.14.0
  - pydantic: 2.13.5
  - fastembed: 0.7.4
  - docling: 2.131.0
  - typesafe-sdk: 0.7.4
  - sse-starlette: 3.5.0
  - python-dotenv: 1.2.3
- Frontend (Node.js v24.14.0, npm 11.9.0):
  - react: 19.2.7
  - react-dom: 19.2.7
  - vite: 8.1.5
  - lucide-react: 1.26.0
  - react-markdown: 10.1.0
  - remark-gfm: 4.0.1
  - remark-math: 6.0.0
  - rehype-katex: 7.0.1
