# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) and answers user questions. It serves as the foundation for more advanced agent capabilities in subsequent tasks.

## LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)
**Model:** `qwen3-coder-plus`

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without VPN
- OpenAI-compatible API interface
- No credit card required

## Configuration

The agent reads configuration from `.env.agent.secret` (gitignored):

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for authentication |
| `LLM_API_BASE` | Base URL of the LLM API endpoint |
| `LLM_MODEL` | Model name to use for completions |

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Command Line   │ ──► │   agent.py   │ ──► │   LLM API       │
│  "Question?"    │     │  (CLI Tool)  │     │  (Qwen Code)    │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  JSON Output │
                        │ {"answer":   │
                        │  "tool_calls"}│
                        └──────────────┘
```

## Data Flow

1. **Input:** User provides a question as command-line argument
2. **Config Loading:** Agent loads `.env.agent.secret` for API credentials
3. **API Call:** HTTP POST request to `{LLM_API_BASE}/chat/completions`
4. **Response Parsing:** Extract answer from `choices[0].message.content`
5. **Output:** Print JSON with `answer` and `tool_calls` fields

## API Request Format

```json
POST {LLM_API_BASE}/chat/completions
Headers:
  Content-Type: application/json
  Authorization: Bearer {LLM_API_KEY}

Body:
{
  "model": "{LLM_MODEL}",
  "messages": [{"role": "user", "content": "<question>"}]
}
```

## Output Format

```json
{
  "answer": "The LLM's response text",
  "tool_calls": []
}
```

**Note:** `tool_calls` is empty in Task 1. It will be populated in Task 2 when tools are added.

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Exit with error message to stderr |
| Missing config values | Exit with error listing missing keys |
| Network timeout (>60s) | Exit with timeout error |
| Connection error | Exit with connection error |
| Invalid API response | Exit with parsing error |

## Usage

```bash
# Basic usage
uv run agent.py "What is REST?"

# Expected output (single JSON line to stdout)
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py -v
```

The test verifies:
- Agent outputs valid JSON
- `answer` field exists and is non-empty
- `tool_calls` field exists and is an array

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script |
| `.env.agent.secret` | Environment configuration (gitignored) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Implementation plan |
| `tests/test_agent.py` | Regression tests |
