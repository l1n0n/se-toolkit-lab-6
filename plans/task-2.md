# Task 2 Plan: The Documentation Agent

## Overview

Extend the Task 1 agent with tools and an agentic loop. The agent will be able to read files and list directories from the project wiki to answer questions with proper source references.

## Tool Definitions

### `read_file`

**Purpose:** Read contents of a file from the project repository.

**Parameters:**
- `path` (string): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message if file doesn't exist.

**Security:** Reject paths containing `../` to prevent directory traversal.

### `list_files`

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated list of entries.

**Security:** Reject paths containing `../` to prevent directory traversal.

## Tool Schema (OpenAI Function Calling)

Tools will be defined as JSON schemas in the LLM API request:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string", "description": "Relative path from project root"}
      },
      "required": ["path"]
    }
  }
}
```

## Agentic Loop

```
1. Send user question + tool schemas to LLM
2. Parse response:
   - If tool_calls present:
     a. Execute each tool with provided arguments
     b. Append tool results as "tool" role messages
     c. Send back to LLM for next iteration
     d. Repeat until no tool_calls or max 10 calls
   - If no tool_calls (final answer):
     a. Extract answer from LLM response
     b. Extract source reference (file path + section)
     c. Output JSON and exit
3. If max 10 tool calls reached → stop and output current answer
```

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read relevant wiki files
3. Extract the answer AND the source reference (file path + section anchor)
4. Include the source in the final answer

Example system prompt:
```
You are a documentation agent that answers questions using the project wiki.

When asked a question:
1. First use list_files to discover what files exist in the wiki/ directory
2. Then use read_file to read relevant files
3. Find the answer and note the exact file path and section
4. Respond with the answer and include the source as: wiki/filename.md#section-anchor

Always include the source reference in your final answer.
```

## Output Format

```json
{
  "answer": "The answer text",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Security

- Validate all paths: reject if contains `../` or starts with `/`
- Ensure resolved path is within project root using `Path.resolve()`
- Return error message for invalid paths instead of raising exceptions

## Testing Strategy

Two regression tests:

1. **Test read_file usage:**
   - Question: "How do you resolve a merge conflict?"
   - Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Test list_files usage:**
   - Question: "What files are in the wiki?"
   - Expected: `list_files` in tool_calls

## Files to Update/Create

- `plans/task-2.md` — this plan
- `agent.py` — add tools and agentic loop
- `AGENT.md` — update documentation
- `tests/test_agent.py` — add 2 more tests
