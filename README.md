# Kanjiro Minimal Context Memory

This repository provides a simple command line tool that keeps a short SQLite-based
conversation memory and generates replies through Gemini or OpenAI.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set environment variables (or edit `.env`):
   - `LLM_PROVIDER` (`gemini` or `openai`, default `gemini`)
   - `GEMINI_API_KEY` / `OPENAI_API_KEY`
   - `GEMINI_MODEL` / `OPENAI_MODEL` (optional)

## Usage
```bash
python main.py --conv <conversation_id> --user "<message>"
```

Example:
```bash
LLM_PROVIDER=gemini GEMINI_API_KEY=xxx python main.py --conv a:b --user "こんにちは"
```

The tool logs each step, stores messages and summaries in `memory.db`, and prints
the final assistant reply to stdout.
