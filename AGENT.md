# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) and answers user questions using an **agentic loop** with tools. The agent can read files and list directories from the project wiki to provide answers with proper source references.

## LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)
**Model:** `qwen3-coder-plus`

**Why Qwen Code:**

- 1000 free requests per day
- Works from Russia without VPN
- OpenAI-compatible API interface
- Supports function/tool calling

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
                               │                      │
                               │◄─────────────────────┤
                               │  tool_calls          │
                               ▼                      │
                        ┌──────────────┐              │
                        │ Execute Tool │──────────────┘
                        │ read_file    │
                        │ list_files   │
                        └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  JSON Output │
                        │ {"answer":   │
                        │  "source":   │
                        │  "tool_calls"}│
                        └──────────────┘
```

## Tools

The agent has two tools to interact with the project filesystem:

### `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**

- `path` (string): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:**

- Rejects paths containing `../` to prevent directory traversal
- Validates resolved path is within project root

### `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**

- `path` (string): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated list of entries.

**Security:**

- Rejects paths containing `../` to prevent directory traversal
- Validates resolved path is within project root

## Tool Schema (OpenAI Function Calling)

Tools are defined as JSON schemas sent to the LLM API:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

## Agentic Loop

The agent implements an iterative loop:

```
1. Send user question + tool schemas to LLM
2. Parse response:
   ┌─ If tool_calls present:
   │  a. Add assistant message with tool_calls to conversation
   │  b. Execute each tool with provided arguments
   │  c. Append tool results as "tool" role messages
   │  d. Send conversation back to LLM (go to step 2)
   │  e. Repeat until no tool_calls OR max 10 calls reached
   │
   └─ If no tool_calls (final answer):
      a. Extract answer from LLM response
      b. Extract source reference (file path + section anchor)
      c. Output JSON and exit
```

### Maximum Tool Calls

The loop stops after **10 tool calls** to prevent infinite loops and excessive API usage.

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read relevant wiki files
3. Extract the answer AND the source reference (file path + section anchor)
4. Include the source in the final answer

```
You are a documentation agent that answers questions using the project wiki.

When asked a question:
1. First use list_files to discover what files exist in the wiki/ directory
2. Then use read_file to read relevant files
3. Find the answer and note the exact file path and section
4. Respond with the answer and include the source as: wiki/filename.md#section-anchor

Always include the source reference in your final answer.
```

## Data Flow

1. **Input:** User provides a question as command-line argument
2. **Config Loading:** Agent loads `.env.agent.secret` for API credentials
3. **Initial LLM Call:** Send question + system prompt + tool schemas
4. **Tool Execution Loop:**
   - Parse tool_calls from LLM response
   - Execute each tool, validate paths for security
   - Append results to conversation as "tool" role messages
   - Send back to LLM for next iteration
5. **Final Answer:** When LLM responds without tool_calls, extract answer and source
6. **Output:** Print JSON with `answer`, `source`, and `tool_calls` fields

## API Request Format

### Initial Request (with tools)

```json
POST {LLM_API_BASE}/chat/completions
Headers:
  Content-Type: application/json
  Authorization: Bearer {LLM_API_KEY}

Body:
{
  "model": "{LLM_MODEL}",
  "messages": [
    {"role": "system", "content": "<system-prompt>"},
    {"role": "user", "content": "<question>"}
  ],
  "tools": [<tool-schemas>]
}
```

### Subsequent Requests (with tool results)

```json
{
  "model": "{LLM_MODEL}",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."}
  ],
  "tools": [<tool-schemas>]
}
```

## Output Format

```json
{
  "answer": "The LLM's response text",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "file1.md\nfile2.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "File contents here..."
    }
  ]
}
```

**Fields:**

- `answer` (string): The final answer from the LLM
- `source` (string): Reference to the wiki section (e.g., `wiki/file.md#section`)
- `tool_calls` (array): All tool calls made during the agentic loop

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing `.env.agent.secret` | Exit with error message to stderr |
| Missing config values | Exit with error listing missing keys |
| Network timeout (>60s) | Exit with timeout error |
| Connection error | Exit with connection error |
| Invalid API response | Exit with parsing error |
| Path traversal attempt | Return error message from tool |
| File not found | Return error message from tool |
| Max tool calls (10) reached | Stop loop, output current answer |

## Security

**Path Validation:**

- Reject paths starting with `/` (absolute paths)
- Reject paths containing `..` (directory traversal)
- Resolve path and verify it's within project root

**No External File Access:**

- Tools only access files within the project directory
- Symlinks and special files are handled safely

## Usage

```bash
# Basic usage
uv run agent.py "How do you resolve a merge conflict?"

# Example output
{
  "answer": "...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [...]
}
```

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:

- Agent outputs valid JSON
- `answer`, `source`, and `tool_calls` fields exist
- Tools are called correctly for specific questions

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script with agentic loop |
| `.env.agent.secret` | Environment configuration (gitignored) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Task 1 implementation plan |
| `plans/task-2.md` | Task 2 implementation plan |
| `tests/test_agent.py` | Regression tests |
