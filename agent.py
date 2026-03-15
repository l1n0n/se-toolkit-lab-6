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
MAX_TOOL_CALLS = 10


def load_config() -> dict:
    """Load configuration from .env.agent.secret."""
    env_path = Path(__file__).parent / ".env.agent.secret"
    if not env_path.exists():
        print(f"Error: {env_path} not found", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_path)

    config = {
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE"),
        "model": os.getenv("LLM_MODEL"),
    }

    missing = [k for k, v in config.items() if not v]
    if missing:
        print(f"Error: Missing config values: {missing}", file=sys.stderr)
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
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


# Tool definitions for LLM API
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to read file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
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
            "description": "List files and directories at a given path. Use this to discover what files exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

# Mapping of tool names to functions
TOOLS_MAP = {
    "read_file": tool_read_file,
    "list_files": tool_list_files,
}

SYSTEM_PROMPT = """You are a documentation agent that answers questions using the project wiki.

When asked a question:
1. First use list_files to discover what files exist in the wiki/ directory
2. Then use read_file to read relevant files
3. Find the answer and note the exact file path and section
4. Respond with the answer and include the source as: wiki/filename.md#section-anchor

Always include the source reference in your final answer. The source should be in the format: path/to/file.md#section-anchor

If you don't know the answer, say so honestly."""


def call_llm(messages: list[dict], config: dict, tools: list | None = None) -> dict:
    """Call the LLM API and return the response."""
    url = f"{config['api_base']}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }

    payload = {
        "model": config["model"],
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
            answer = choice.get("content", "")

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

    # If we exit loop without final answer, use last content or generate one
    print(f"Exiting loop after {tool_call_count} tool calls", file=sys.stderr)

    # Try to get a final answer
    messages.append(
        {
            "role": "user",
            "content": "Based on the tool results above, please provide your final answer with the source reference.",
        }
    )

    response = call_llm(messages, config, tools=None)
    answer = response["choices"][0]["message"].get("content", "")
    source = extract_source(answer)

    return answer, source, all_tool_calls


def extract_source(answer: str) -> str:
    """
    Extract source reference from the answer.
    Looks for patterns like wiki/file.md#section or wiki/file.md
    """
    import re

    # Look for markdown-style references: wiki/file.md#section or wiki/file.md
    pattern = r"(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)"
    match = re.search(pattern, answer)

    if match:
        return match.group(1)

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
