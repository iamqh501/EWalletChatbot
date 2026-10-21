# Project Mistakes and Caveats

## Python Virtual Environment DLL Mismatch After Host Python Upgrade
Problem: DLL load failure on importing ctypes (ImportError: DLL load failed while importing _ctypes: The specified procedure could not be found) when running python or uvicorn from .venv on Windows 11.
Cause: Host Python 3.14 was upgraded to build 3.14.8, while .venv Scripts retained older binary runtime copies (python314.dll, _ctypes.pyd, libffi-8.dll). The ABI mismatch between host standard library modules and virtualenv binaries prevented C-extensions from loading.
Fix: Copied updated python314.dll, python.exe, pythonw.exe, vcruntime DLLs, and standard extension .pyd and .dll files from Python314 root and DLLs folder into .venv/Scripts.

## Unsupported Hugging Face Router Model Identifier
Problem: Configuring HF_LLM_MODEL_NAME to Qwen/Qwen3-8B:fastest caused HTTP 400 model_not_supported.
Cause: The specified model tag was not hosted or recognized on the Hugging Face Router endpoint.
Fix: Switched to verified supported router model tags, such as Qwen/Qwen3.5-9B:deepinfra or inclusionAI/Ling-3.0-flash:fastest.

## Degraded Retrieval Accuracy on Direct Child Chunk Reranking
Problem: Reranking child chunks directly against user queries gave low and inconsistent scores (0.59 to 0.70) because markdown tables and fee lists were severed across chunk boundaries.
Cause: Child chunks only contain partial table fragments without headers or sufficient context for the reranker to calculate semantic similarity accurately.
Fix: Implemented Parent-Child retrieval where Qdrant searches child vectors to retrieve doc_ids, deduplicates parent document IDs, fetches full parent documents from storage, and passes intact parent text to Jev Reranker. Relevancy scores improved to 0.98.

## Thinking Tag and Token Leaks in Streaming Response
Problem: Closing think tags prematurely during tool calling or empty token chunks caused internal reasoning tags (<think>...</think>) to spill into the user-facing response. Multiple think blocks also caused display anomalies in the frontend.
Cause: The streaming loop closed think tags upon encountering whitespace tokens prior to tool execution, emitting premature closing tags.
Fix: Maintained in_thinking state across tool executions so thinking remained contiguous, stripped raw think tags from outgoing reasoning stream, and upgraded frontend parseMessage logic to isolate all think blocks into the dedicated thinking component.

## Frontend Markdown Table Formatting and HTML Line Break Handling
Problem: ReactMarkdown rendered tables on a single plain text line, and raw br HTML tags appeared as unrendered text strings.
Cause: react-markdown requires the remark-gfm plugin to parse GitHub Flavored Markdown tables, and standard ReactMarkdown escapes raw HTML tags by default.
Fix: Added remark-gfm plugin to ReactMarkdown, styled table elements with CSS (including vertical-align: top for multi-line cells), and added a custom component renderer to convert raw br strings into React JSX br elements.

## Frontend Interface Freeze on Empty SSE Tokens
Problem: Receiving empty string tokens from the SSE stream caused premature clearing of systemStatus in the frontend UI, freezing the chat interface.
Cause: The frontend cleared its loading indicator upon receiving any token event, even if the payload token was empty.
Fix: Updated App.jsx to only clear systemStatus when the received token text is non-empty.

## Query Rewrite Tool Latency and Redundancy
Problem: Using a dedicated query rewrite tool added an extra LLM roundtrip, increasing response latency and causing occasional hallucination of user intent.
Cause: Generating rewritten queries via an additional LLM call is unnecessary when conversation history can be evaluated directly for semantic relevance.
Fix: Removed the query rewrite tool entirely. Implemented HistoryScorer using TypeSafe Jev (Noul) and the Harmonic Bridge formula (d_bridge_ij = 2 x d_i x r_ij / (d_i + r_ij), u_i = 0.5 x d_i + 0.5 x avg(d_bridge_ij)), filtering relevant messages with threshold u_i >= 0.7 into the prompt context.

## Ambiguous Query Handling Causing Hallucinations or Incorrect Tool Selection
Problem: Vague queries with missing subjects or pronouns caused LLMs to trigger wrong search tools or hallucinate responses.
Cause: LLM router was forced to choose between general search or telecom package search without a structured mechanism to assess uncertainty.
Fix: Introduced the resolve_intent tool executing a 3-step reasoning framework (Hypotheses, Evidence Evaluation, Decision). If confidence is low, the agent asks a short clarifying question instead of executing irrelevant database searches.

## Vector Dimension Mismatch on Embedding Migration
Problem: Migrating from local sentence-transformers (384 dimensions) to Hugging Face google/embeddinggemma-300m (768 dimensions) caused vector dimension mismatch errors in existing Qdrant collections.
Cause: Qdrant collections require vector size definitions at creation time; vectors with differing dimensions cannot be inserted into the same collection.
Fix: Rebuilt Qdrant collection with 768 dimensions using index_docs.py --mode reset and batched document embedding with batch size 32.

## Single Prompt Interference Between Tool Selection and Output Formatting
Problem: Combining tool selection rules with strict output formatting constraints (e.g. do not summarize, keep table structure, do not comment) in a single system prompt degraded tool argument extraction and caused format violations.
Cause: Conflicting instructions in one prompt overloaded LLM attention during tool schema binding.
Fix: Separated into two distinct LLM calls: Call 1 uses TOOL_ROUTING_SYSTEM_PROMPT focused exclusively on intent and tool selection; Call 2 uses FINAL_RESPONSE_SYSTEM_PROMPT focused exclusively on synthesizing the answer from retrieved context.

## Local Llama Server Instability on Consumer GPU
Problem: Local llama-server.exe processes experienced frequent crashes or timeouts due to unstable laptop GPU VRAM (RTX 3050 Ti 4GB).
Cause: Low VRAM headroom and unstable GPU drivers under heavy inference load.
Fix: Deprecated local llama-server and switched to remote Hugging Face Router API (https://router.huggingface.co/v1) using LangChain ChatDeepSeek with stream_usage=True and CPU fallback for local embeddings.


## Relative Import and Type Mismatch in Environment Loader
Problem: Importing backend.core.env failed with ModuleNotFoundError: No module named 'config' and TypeError on path operations.
Cause: backend/core/env.py attempted to import config directly instead of backend.core.config, and attempted to use the slash operator on string BASE_DIR instead of os.path.join or pathlib.Path.
Fix: Updated import to from backend.core.config import BASE_DIR, constructed ENV_FILE with os.path.join(BASE_DIR, ".env"), added exists check, and ensured bidirectional mapping between HF_API_KEY and HF_TOKEN.

## Typographical Error in Hugging Face Router VLM Identifier
Problem: Configuring HF_VLM_MODEL_NAME to iinclusionAI/Ling-3.0-flash-VL:fastest failed with HTTP 400 model_not_found.
Cause: Provider namespace contained a duplicate leading character (iinclusionAI instead of inclusionAI).
Fix: Fixed model tag to inclusionAI/Ling-3.0-flash-VL:fastest and implemented prefix sanitization in backend/core/env.py and backend/services/llm.py to automatically correct duplicate leading characters.

## Indented Markdown Headers Breaking Text Splitter
Problem: Markdown headers with leading spaces (e.g.   ## Tác vụ:) were ignored by MarkdownHeaderTextSplitter, causing adjacent sections to merge into one chunk.
Cause: MarkdownHeaderTextSplitter requires header markers to start at the first character of each line.
Fix: Added pre-processing line normalization in index_docs.py to strip leading indentation before header hashes (# , ## , ### ) prior to splitting.

## Missing Data Purchase Section in App Instructions Document
Problem: docs/cach_dung_app.md contained a duplicate Top-up section instead of a Data 4G/5G purchase task, preventing retrieval of data registration instructions.
Cause: Copy-paste duplication during manual knowledge drafting.
Fix: Corrected the duplicate block to Tác vụ: Mua gói cước Data 4G/5G with required_screen_id DATA_4G_5G, mirrored to docs/cach_dung_ap.md, and ran index_docs.py --mode update to refresh parent documents and vector embeddings.

## App Screen Coupling in Vision-Language Prompt
Problem: Hardcoding specific app screen IDs and layout descriptions in the VLM prompt created tight coupling, requiring prompt modifications whenever app interfaces change.
Cause: VLM_REWRITE_SYSTEM_PROMPT initially contained explicit application screens (HOME, DATA_4G_5G, TOPUP_PHONE) and specific UI element assumptions.
Fix: Generalized VLM_REWRITE_SYSTEM_PROMPT into an agnostic visual inspection and query rewriting instruction focusing purely on visible text, labels, amounts, and UI elements without hardcoded application screens.

## Static Screen Normalization in Navigation Tool
Problem: Hardcoded string checks in normalize_screen_id caused tool rigidity and potential divergence when screen definitions or titles changed.
Cause: Navigation tool used fixed branching instead of querying navigation_map.json metadata.
Fix: Implemented dynamic resolve_screen_id and build_navigation_path functions that inspect screens, titles, visual_cues, and global_navigation definitions loaded directly from navigation_map.json.
