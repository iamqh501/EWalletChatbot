# index_docs.py

CLI tool for managing the vector knowledge base (Qdrant & LocalFileStore) and preprocessing document data for RAG retrieval.

## Syntax

```bash
python index_docs.py --mode <reset|update|convert> [OPTIONS]
# Or using shorthand flags:
python index_docs.py --reset | --update | --convert [OPTIONS]
```

---

## Modes

### `reset` (`--reset`)
Wipes existing vector collections, parent stores, and state files, then re-indexes all Markdown files in `docs/` from scratch.
> Automatically skips `.xlsx` and `.json` files.

```bash
python index_docs.py --mode reset
```

### `update` (`--update`)
Incrementally syncs the database by comparing file MD5 hashes against `docs/file_state.json`:

| Change | Action |
|---|---|
| **Added** | Indexes new document into Qdrant & store |
| **Modified** | Purges old chunks, re-indexes updated content |
| **Deleted** | Removes obsolete chunks from Qdrant & store |
| **Unchanged** | Skips indexing |

> Automatically falls back to full `reset` if previous state or collection is missing.

```bash
python index_docs.py --mode update
```

### `convert` (`--convert`)
Converts data plan spreadsheets into standardized JSON format (`{ "id": "pkg_xxx", "metadata": { ... } }`).

```bash
python index_docs.py --mode convert
```

---

## Options

| Flag | Applicable Modes | Description |
|---|---|---|
| `--export-chunks <DIR>` | `reset`, `update` | Exports parent chunks to `<DIR>` using the source file name. |
| `--excel <PATH>` | `convert` | Input Excel path (default: `docs/goi_cuoc.xlsx`). |
| `--json <PATH>` | `convert` | Output JSON path (default: `docs/goi_cuoc.json`). |

---

## Examples

```bash
# Rebuild index and export chunks for inspection
python index_docs.py --reset --export-chunks chunks_output

# Sync changes after editing docs
python index_docs.py --update

# Convert custom Excel file
python index_docs.py --convert --excel custom_plans.xlsx --json docs/goi_cuoc.json
```
