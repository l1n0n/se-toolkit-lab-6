# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) and answers user questions using an **agentic loop** with tools. The agent can:

1. Read files and list directories from the project wiki
2. Query the deployed backend API for runtime data
3. Provide answers with proper source references

## LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)
**Model:** `qwen3-coder-plus`

**Why Qwen Code:**

- 1000 free requests per day
- Works from Russia without VPN
- OpenAI-compatible API interface
- Supports function/tool calling

## Configuration

The agent reads configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for backend API (default: `http://localhost:42002`) | `.env.docker.secret` or env |

**Important:** The autochecker injects its own values at runtime. Never hardcode these values.

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
                        │ query_api    │
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

The agent has three tools to interact with the project:

### `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**

- `path` (string): Relative path from project root (e.g., `wiki/git-workflow.md`, `backend/app/routers/items.py`)

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:**

- Rejects paths containing `../` to prevent directory traversal
- Validates resolved path is within project root

### `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**

- `path` (string): Relative directory path from project root (e.g., `wiki`, `backend/app/routers`)

**Returns:** Newline-separated list of entries (filtered for code directories).

**Security:**

- Rejects paths containing `../` to prevent directory traversal
- Validates resolved path is within project root

### `query_api`

**Purpose:** Call the backend API to query data, check system behavior, or test endpoints.

**Parameters:**

- `method` (string): HTTP method (GET, POST, PUT, DELETE, PATCH)
- `path` (string): API endpoint path (e.g., `/items/`, `/analytics/completion-rate?lab=lab-99`)
- `body` (string, optional): JSON request body for POST/PUT/PATCH requests
- `authorize` (boolean, default: true): Whether to include Authorization header. Set to `false` to test unauthenticated access.

**Returns:** JSON string with `status_code` and `body`, or error message.

**Authentication:** Uses `LMS_API_KEY` from environment for `Authorization: Bearer` header (when `authorize=true`).

**Example usage:**

```bash
# Query database
GET /items/

# Check status code without auth
GET /items/ (authorize=false) → 401

# Get analytics
GET /analytics/completion-rate?lab=lab-01

# Test error conditions
GET /analytics/completion-rate?lab=lab-99 → 500 (ZeroDivisionError)
```

## Tool Schema (OpenAI Function Calling)

Tools are defined as JSON schemas sent to the LLM API:

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the backend API to query data...",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
        },
        "path": {
          "type": "string",
          "description": "API endpoint path"
        },
        "authorize": {
          "type": "boolean",
          "description": "Whether to include Authorization header",
          "default": true
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

## Agentic Loop

The agent implements an iterative loop:

```
1. Send user question + system prompt + tool schemas to LLM
2. Parse response:
   ┌─ If tool_calls present:
   │  a. Add assistant message with tool_calls to conversation
   │  b. Execute each tool with provided arguments
   │  c. Append tool results as "tool" role messages
   │  d. Send conversation back to LLM (go to step 2)
   │  e. Repeat until no tool_calls OR max 20 calls reached
   │
   └─ If no tool_calls (final answer):
      a. Check if answer is complete (not too short)
      b. Extract source reference (file path + section anchor)
      c. Output JSON and exit
```

### Maximum Tool Calls

The loop stops after **20 tool calls** to prevent infinite loops and excessive API usage.

### Incomplete Answer Detection

If the LLM returns a very short answer (<50 chars) starting with "Let me..." or "I'll...", the agent asks for a complete final answer before exiting.

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read relevant wiki files or source code
3. Use `query_api` for runtime data, status codes, and API behavior
4. Extract the answer AND the source reference (file path + section anchor)
5. Include the source in the final answer

```
You are a documentation and system agent that answers questions using:
1. The project wiki (via list_files and read_file tools)
2. The running backend API (via query_api tool)
3. The source code (via read_file tool)

Tool selection guidance:
- Use list_files to discover what files exist in a directory
- Use read_file to read wiki documentation or source code files
- Use query_api to:
  - Query the database (GET /items/)
  - Check API behavior (status codes, errors, responses)
  - Get analytics data (GET /analytics/*)
  - Test endpoints and check authentication

When answering:
1. Choose the right tool for the question type:
   - Wiki/documentation questions → read_file on wiki/*.md
   - System/runtime questions → query_api on backend endpoints
   - Code questions → read_file on backend/app/*.py or backend/app/routers/*.py
2. ALWAYS include a source reference at the end of your answer
3. For API questions, report actual data from the API response
4. For code questions, read the relevant files and explain based on what you find
```

## Data Flow

1. **Input:** User provides a question as command-line argument
2. **Config Loading:** Agent loads environment variables for API credentials
3. **Initial LLM Call:** Send question + system prompt + tool schemas
4. **Tool Execution Loop:**
   - Parse tool_calls from LLM response
   - Execute each tool, validate paths for security
   - Append results to conversation as "tool" role messages
   - Send back to LLM for next iteration
5. **Final Answer:** When LLM responds without tool_calls, extract answer and source
6. **Output:** Print JSON with `answer`, `source`, and `tool_calls` fields

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
    },
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

**Fields:**

- `answer` (string): The final answer from the LLM
- `source` (string): Reference to the source file (e.g., `wiki/file.md#section` or `backend/app/routers/file.py`)
- `tool_calls` (array): All tool calls made during the agentic loop

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing environment config | Exit with error message to stderr |
| Missing config values | Exit with error listing missing keys |
| Network timeout (>60s) | Exit with timeout error |
| Connection error | Exit with connection error |
| Invalid API response | Exit with parsing error |
| Path traversal attempt | Return error message from tool |
| File not found | Return error message from tool |
| Max tool calls (20) reached | Stop loop, output current answer |
| Incomplete answer detected | Ask LLM for complete final answer |

## Security

**Path Validation:**

- Reject paths starting with `/` (absolute paths)
- Reject paths containing `..` (directory traversal)
- Resolve path and verify it's within project root

**API Authentication:**

- `query_api` uses `LMS_API_KEY` from environment
- Can disable auth with `authorize=false` for testing

**No External File Access:**

- Tools only access files within the project directory
- Symlinks and special files are handled safely

## Usage

```bash
# Basic usage
uv run agent.py "How many items are in the database?"

# Example output
{
  "answer": "There are 44 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

## Benchmark Performance

**Local evaluation score: 8/10 (80%)**

### Passing Questions

1. ✓ Wiki: Protect a branch on GitHub
2. ✓ Wiki: SSH connection to VM
3. ✓ Code: Python web framework (FastAPI)
4. ✓ Code: API router modules
5. ✓ API: Item count in database
6. ✓ API: Status code without auth (401)
7. ✓ API + Code: ZeroDivisionError in completion-rate

### Failing Questions (LLM Judge)

8. ✗ API + Code: TypeError in top-learners endpoint
2. ✗ Multi-file: HTTP request journey (docker-compose, Dockerfile, Caddyfile, main.py)
3. ✗ Code: ETL idempotency

### Lessons Learned

1. **Tool descriptions matter:** Clear descriptions help LLM choose the right tool
2. **Authorize parameter:** Essential for testing unauthenticated endpoints
3. **Incomplete answer detection:** Prevents premature exits but can cause loops
4. **LLM judge questions:** Require longer, structured answers that the current agent struggles to produce
5. **Multi-file synthesis:** Agent needs better guidance for combining information from multiple sources

### Future Improvements

1. Add explicit "synthesize" step after reading multiple files
2. Improve handling of open-ended reasoning questions
3. Better detection of when to stop reading and start answering
4. Add support for following up on error messages automatically

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:

- Agent outputs valid JSON
- `answer`, `source`, and `tool_calls` fields exist
- Tools are called correctly for specific questions
- `query_api` works for data queries
- `read_file` works for code questions

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script with agentic loop |
| `.env.agent.secret` | LLM environment configuration (gitignored) |
| `.env.docker.secret` | Backend API environment configuration (gitignored) |
| `AGENT.md` | This documentation |
| `plans/task-1.md` | Task 1 implementation plan |
| `plans/task-2.md` | Task 2 implementation plan |
| `plans/task-3.md` | Task 3 implementation plan with benchmark results |
| `tests/test_agent.py` | Regression tests (5 total) |
