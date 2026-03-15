#!/usr/bin/env python3
"""
Agent CLI - connects to an LLM and answers questions.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer' and 'tool_calls' fields to stdout.
    All debug output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


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


def call_llm(question: str, config: dict) -> str:
    """Call the LLM API and return the answer."""
    url = f"{config['api_base']}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }
    
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": question}],
    }
    
    print(f"Calling LLM at {url}...", file=sys.stderr)
    
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
    except httpx.TimeoutException:
        print("Error: LLM request timed out (>60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Failed to connect to LLM: {e}", file=sys.stderr)
        sys.exit(1)
    
    data = response.json()
    
    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"Error: Unexpected API response format: {e}", file=sys.stderr)
        print(f"Response: {data}", file=sys.stderr)
        sys.exit(1)
    
    return answer


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    config = load_config()
    answer = call_llm(question, config)
    
    result = {
        "answer": answer,
        "tool_calls": [],
    }
    
    print(json.dumps(result))


if __name__ == "__main__":
    main()
