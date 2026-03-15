# Task 3 Plan: The System Agent

## Overview

Extend the Task 2 agent with a `query_api` tool to interact with the deployed backend API. This enables the agent to answer questions about the running system (framework, ports, status codes) and data-dependent queries (item count, scores, analytics).

## New Tool: `query_api`

**Purpose:** Call the deployed backend API and return the response.

**Parameters:**

- `method` (string): HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` (string): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body` (parsed response).

**Authentication:** Use `LMS_API_KEY` from environment for `Authorization: Bearer` header.

**Configuration:**

- `AGENT_API_BASE_URL`: Base URL for the backend API (default: `http://localhost:42002`)
- Read from environment variables, not hardcoded

## Tool Schema (OpenAI Function Calling)

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the backend API to query data or check system behavior. Use this for questions about the running system, database contents, or API responses.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, etc.)",
          "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
        },
        "path": {
          "type": "string",
          "description": "API endpoint path (e.g., '/items/', '/analytics/top-learners')"
        },
        "body": {
          "type": "string",
          "description": "Optional JSON request body for POST/PUT requests"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

## Environment Variables

The agent reads all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (optional) | `.env.docker.secret` or default |

**Important:** The autochecker injects its own values at runtime. Never hardcode these values.

## System Prompt Updates

Update the system prompt to guide the LLM on when to use each tool:

```
You are a documentation and system agent that answers questions using:
1. The project wiki (via list_files and read_file tools)
2. The running backend API (via query_api tool)
3. The source code (via read_file tool)

Tool selection guidance:
- Use list_files to discover what files exist
- Use read_file to read wiki documentation or source code
- Use query_api to:
  - Query the database (GET /items/)
  - Check API behavior (status codes, errors)
  - Get analytics data
  - Test endpoints

When answering:
1. Choose the right tool for the question
2. For wiki questions: use read_file on wiki/*.md files
3. For system questions: use query_api on the backend
4. For code questions: use read_file on backend/*.py files
5. Include source references when applicable

Always provide accurate answers based on actual data from tools.
```

## Implementation Steps

1. **Add `query_api` function:**
   - Read `LMS_API_KEY` and `AGENT_API_BASE_URL` from environment
   - Build HTTP request with authentication
   - Return JSON response with status_code and body

2. **Register tool schema:**
   - Add to `TOOLS_SCHEMA` list
   - Add to `TOOLS_MAP` dictionary

3. **Update system prompt:**
   - Add guidance on when to use `query_api` vs wiki tools

4. **Update configuration loading:**
   - Read `LMS_API_KEY` from `.env.docker.secret`
   - Read `AGENT_API_BASE_URL` (with default fallback)

5. **Run benchmark:**
   - Execute `uv run run_eval.py`
   - Fix failing questions iteratively
   - Document results in plan

## Benchmark Results

First run score: **8/10 passed**

### Failures

**Question 8** (LLM judge): "The /analytics/top-learners endpoint crashes for some labs..."

- Issue: Agent finds the error but doesn't provide complete explanation
- Fix needed: Improve final answer generation for reasoning questions

**Question 9** (LLM judge): "Read docker-compose.yml and backend Dockerfile..."

- Issue: Agent gets stuck in file reading loop, doesn't produce final answer
- Fix needed: Better handling of multi-file synthesis questions

### Iteration Strategy

1. For LLM judge questions, ensure agent produces longer, structured answers
2. Add explicit instruction to synthesize information from multiple files
3. Consider adding a "summarize" step after reading all relevant files

## Testing Strategy

Add 2 regression tests:

1. **Test read_file for framework question:**
   - Question: "What framework does the backend use?"
   - Expected: `read_file` in tool_calls, answer contains "FastAPI"

2. **Test query_api for data question:**
   - Question: "How many items are in the database?"
   - Expected: `query_api` in tool_calls, answer contains a number > 0

## Files to Update/Create

- `plans/task-3.md` — this plan (update with benchmark results)
- `agent.py` — add `query_api` tool, update config loading
- `AGENT.md` — document new tool and lessons learned
- `tests/test_agent.py` — add 2 more tests

## Security Considerations

- `query_api` should only access the configured backend URL
- No arbitrary URL access (prevent SSRF)
- Authentication token from environment only
