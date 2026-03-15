#!/usr/bin/env python3
"""
Agent CLI - connects to an LLM and answers questions using tools.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source', and 'tool_calls' fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 20


def load_config() -> dict:
    """Load configuration from environment files."""
    # Load LLM config from .env.agent.secret
    llm_env_path = Path(__file__).parent / ".env.agent.secret"
    if llm_env_path.exists():
        load_dotenv(llm_env_path, override=True)

    # Load LMS API config from .env.docker.secret
    lms_env_path = Path(__file__).parent / ".env.docker.secret"
    if lms_env_path.exists():
        load_dotenv(lms_env_path, override=True)

    config = {
        # LLM configuration
        "llm_api_key": os.getenv("LLM_API_KEY"),
        "llm_api_base": os.getenv("LLM_API_BASE"),
        "llm_model": os.getenv("LLM_MODEL"),
        # Backend API configuration
        "lms_api_key": os.getenv("LMS_API_KEY"),
        "agent_api_base_url": os.getenv("AGENT_API_BASE_URL", "http://localhost:42002"),
    }

    # Check required LLM values
    llm_missing = [
        k for k in ["llm_api_key", "llm_api_base", "llm_model"] if not config.get(k)
    ]
    if llm_missing:
        print(f"Error: Missing LLM config values: {llm_missing}", file=sys.stderr)
        sys.exit(1)

    return config


def validate_path(path: str) -> tuple[bool, str]:
    """
    Validate that a path is safe and within the project directory.
    Returns (is_valid, error_message).
    """
    if not path:
        return False, "Path cannot be empty"

    if path.startswith("/"):
        return False, "Path cannot be absolute"

    if ".." in path:
        return False, "Path cannot contain '..' (directory traversal not allowed)"

    return True, ""


def tool_read_file(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    project_root = Path(__file__).parent
    file_path = project_root / path

    # Resolve to absolute path and verify it's within project root
    try:
        resolved_path = file_path.resolve()
        resolved_root = project_root.resolve()
        if not str(resolved_path).startswith(str(resolved_root)):
            return "Error: Path traversal detected"
    except Exception as e:
        return f"Error: {e}"

    if not file_path.exists():
        return f"Error: File not found: {path}"

    if not file_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def tool_list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated list of entries, or error message
    """
    is_valid, error = validate_path(path)
    if not is_valid:
        return f"Error: {error}"

    project_root = Path(__file__).parent
    dir_path = project_root / path

    # Resolve to absolute path and verify it's within project root
    try:
        resolved_path = dir_path.resolve()
        resolved_root = project_root.resolve()
        if not str(resolved_path).startswith(str(resolved_root)):
            return "Error: Path traversal detected"
    except Exception as e:
        return f"Error: {e}"

    if not dir_path.exists():
        return f"Error: Directory not found: {path}"

    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted([e.name for e in dir_path.iterdir()])
        # Filter out __init__.py and directories for code directories
        if "routers" in path or "backend" in path:
            entries = [e for e in entries if e.endswith(".py") and e != "__init__.py"]
        result = "\n".join(entries)
        # Add hint for LLM to read all files
        if entries:
            result += f"\n\n[Hint: To answer questions about this directory, read each file using read_file]"
        return result
    except Exception as e:
        return f"Error listing directory: {e}"


def tool_query_api(
    method: str, path: str, body: str | None = None, authorize: bool = True
) -> str:
    """
    Call the backend API and return the response.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path (e.g., '/items/')
        body: Optional JSON request body
        authorize: Whether to include Authorization header (default: True)

    Returns:
        JSON string with status_code and body, or error message
    """
    # Get API base URL from config (set via environment)
    api_base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY")

    url = f"{api_base}{path}"

    headers = {
        "Content-Type": "application/json",
    }

    # Only include Authorization header if authorize=True and api_key is set
    if authorize and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"Calling API: {method} {url} (authorize={authorize})", file=sys.stderr)

    try:
        if method.upper() == "GET":
            response = httpx.get(url, headers=headers, timeout=30.0)
        elif method.upper() == "POST":
            data = json.loads(body) if body else None
            response = httpx.post(url, headers=headers, json=data, timeout=30.0)
        elif method.upper() == "PUT":
            data = json.loads(body) if body else None
            response = httpx.put(url, headers=headers, json=data, timeout=30.0)
        elif method.upper() == "DELETE":
            response = httpx.delete(url, headers=headers, timeout=30.0)
        elif method.upper() == "PATCH":
            data = json.loads(body) if body else None
            response = httpx.patch(url, headers=headers, json=data, timeout=30.0)
        else:
            return f"Error: Unknown method: {method}"

        result = {
            "status_code": response.status_code,
            "body": response.text,
        }

        return json.dumps(result)

    except httpx.TimeoutException:
        return f"Error: API request timed out"
    except httpx.ConnectError as e:
        return f"Error: Cannot connect to API at {url}: {e}"
    except json.JSONDecodeError:
        return f"Error: Invalid JSON in body parameter"
    except Exception as e:
        return f"Error: {e}"


# Tool definitions for LLM API
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to read wiki documentation or source code files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md' or 'backend/main.py')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Use this to discover what files exist in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki' or 'backend')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API to query data, check system behavior, or test endpoints. Use this for questions about the running system, database contents, API responses, status codes, or analytics data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate', '/items/1/')",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT/PATCH requests",
                    },
                    "authorize": {
                        "type": "boolean",
                        "description": "Whether to include Authorization header (default: true). Set to false to test unauthenticated access.",
                        "default": True,
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]

# Mapping of tool names to functions
TOOLS_MAP = {
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "query_api": tool_query_api,
}

SYSTEM_PROMPT = """You are a documentation and system agent that answers questions using:
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

query_api parameters:
- method: HTTP method (GET, POST, PUT, DELETE, PATCH)
- path: API endpoint path (e.g., '/items/', '/analytics/completion-rate')
- body: Optional JSON request body for POST/PUT/PATCH
- authorize: Whether to include Authorization header (default: true). Set authorize=false to test unauthenticated access and see 401 responses.

When answering:
1. Choose the right tool for the question type:
   - Wiki/documentation questions → read_file on wiki/*.md
   - System/runtime questions → query_api on backend endpoints
   - Code questions → read_file on backend/app/*.py or backend/app/routers/*.py
2. ALWAYS include a source reference at the end of your answer in this exact format:
   - For wiki files: wiki/filename.md#section-anchor
   - For code files: path/to/file.py
   Example: "The answer is... wiki/github.md#branch-protection"
3. For API questions, report actual data from the API response
4. For code questions, read the relevant files and explain based on what you find

Important paths:
- Wiki files: wiki/*.md
- Backend code: backend/app/*.py, backend/app/routers/*.py
- Backend routers: backend/app/routers/items.py, backend/app/routers/interactions.py, backend/app/routers/analytics.py, backend/app/routers/pipeline.py, backend/app/routers/learners.py

Always provide accurate answers based on actual data from tools, not assumptions. Give complete answers that address all parts of the question."""


def call_llm(messages: list[dict], config: dict, tools: list | None = None) -> dict:
    """Call the LLM API and return the response."""
    url = f"{config['llm_api_base']}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['llm_api_key']}",
    }

    payload = {
        "model": config["llm_model"],
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
    response.raise_for_status()

    return response.json()


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    if tool_name not in TOOLS_MAP:
        return f"Error: Unknown tool: {tool_name}"

    tool_func = TOOLS_MAP[tool_name]
    return tool_func(**args)


def run_agentic_loop(question: str, config: dict) -> tuple[str, str, list[dict]]:
    """
    Run the agentic loop: LLM → tool calls → execute → loop until answer.

    Returns:
        (answer, source, tool_calls)
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls = []
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        print(f"Calling LLM (iteration {tool_call_count + 1})...", file=sys.stderr)

        response = call_llm(messages, config, tools=TOOLS_SCHEMA)

        choice = response["choices"][0]["message"]

        # Check if LLM wants to call tools
        tool_calls = choice.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - this is the final answer
            answer = choice.get("content") or ""

            # Check if answer looks incomplete (only for very short answers)
            # An answer is likely incomplete if it's under 50 chars and starts with "Let me"
            is_very_short = len(answer) < 50
            starts_with_delay = (
                answer.lower().strip().startswith(("let me", "let's", "i'll", "i will"))
            )

            # If answer seems incomplete and we haven't hit max calls, ask for final answer
            if (
                is_very_short
                and starts_with_delay
                and tool_call_count < MAX_TOOL_CALLS - 2
            ):
                print(
                    f"Answer seems incomplete, asking for final answer...",
                    file=sys.stderr,
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Please provide your complete final answer now.",
                    }
                )
                continue

            # Extract source from answer (look for pattern like wiki/file.md#section)
            source = extract_source(answer)

            print(f"Final answer received", file=sys.stderr)
            return answer, source, all_tool_calls

        # Add assistant message with tool_calls to messages
        messages.append(choice)

        # Execute tool calls
        for tool_call in tool_calls:
            tool_call_count += 1

            if tool_call_count > MAX_TOOL_CALLS:
                print(f"Max tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)
                break

            function = tool_call["function"]
            tool_name = function["name"]
            tool_args = json.loads(function["arguments"])

            print(f"Executing tool: {tool_name}({tool_args})", file=sys.stderr)

            result = execute_tool(tool_name, tool_args)

            # Record tool call
            all_tool_calls.append(
                {
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                }
            )

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                }
            )

        if tool_call_count >= MAX_TOOL_CALLS:
            break

    # If we exit loop without final answer, try to get one
    print(f"Exiting loop after {tool_call_count} tool calls", file=sys.stderr)

    # Try to get a final answer
    messages.append(
        {
            "role": "user",
            "content": "Based on the tool results above, please provide your final answer.",
        }
    )

    response = call_llm(messages, config, tools=None)
    answer = response["choices"][0]["message"].get("content") or ""
    source = extract_source(answer)

    return answer, source, all_tool_calls


def extract_source(answer: str) -> str:
    """
    Extract source reference from the answer.
    Looks for patterns like wiki/file.md#section or wiki/file.md or backend/app/routers/file.py
    """
    import re

    # First look for explicit wiki references: wiki/file.md#section or wiki/file.md
    pattern = r"(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)"
    match = re.search(pattern, answer)

    if match:
        return match.group(1)

    # Look for backend file references: backend/app/routers/file.py
    pattern2 = r"(backend/[\w\-/]+\.py)"
    match2 = re.search(pattern2, answer)

    if match2:
        return match2.group(1)

    # Look for references like `github.md` or `file.md` mentioned in backticks
    pattern3 = r"`([\w\-/]+\.md)(?:#([\w\-]+))?`"
    match3 = re.search(pattern3, answer)

    if match3:
        filename = match3.group(1)
        anchor = match3.group(2)
        # Assume wiki/ for common wiki files
        if filename in [
            "github.md",
            "git.md",
            "git-workflow.md",
            "git-vscode.md",
            "gitlens.md",
        ]:
            if anchor:
                return f"wiki/{filename}#{anchor}"
            return f"wiki/{filename}"
        return filename

    # Look for file.md#section or file.md patterns without backticks
    pattern4 = r"\b([\w\-]+\.md)(?:#([\w\-]+))?\b"
    match4 = re.search(pattern4, answer)

    if match4:
        filename = match4.group(1)
        anchor = match4.group(2)
        # Assume wiki/ for common wiki files
        if filename in [
            "github.md",
            "git.md",
            "git-workflow.md",
            "git-vscode.md",
            "gitlens.md",
            "ssh.md",
            "vm.md",
        ]:
            if anchor:
                return f"wiki/{filename}#{anchor}"
            return f"wiki/{filename}"

    # If no source found, return empty string
    return ""


def main():
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "Your question here"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    config = load_config()
    answer, source, tool_calls = run_agentic_loop(question, config)

    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
