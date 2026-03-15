"""
Regression tests for agent.py

Tests verify that the agent:
- Outputs valid JSON
- Has required 'answer', 'source', and 'tool_calls' fields
- Uses tools correctly for specific questions
"""

import json
import subprocess
import sys


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields (Task 1)."""
    result = subprocess.run(
        ["uv", "run", "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, (
        f"Agent exited with code {result.returncode}: {result.stderr}"
    )

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Invalid JSON output: {e}\nStdout: {result.stdout}\nStderr: {result.stderr}"
        )

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must be non-empty"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"


def test_agent_uses_read_file_for_merge_conflict_question():
    """Test that agent uses read_file tool when asked about merge conflicts (Task 2)."""
    result = subprocess.run(
        ["uv", "run", "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, (
        f"Agent exited with code {result.returncode}: {result.stderr}"
    )

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Invalid JSON output: {e}\nStdout: {result.stdout}\nStderr: {result.stderr}"
        )

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must be non-empty"

    assert "source" in output, "Missing 'source' field in output"
    assert isinstance(output["source"], str), "'source' must be a string"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Check that read_file was used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "read_file" in tool_names, (
        f"Expected 'read_file' in tool_calls, got: {tool_names}"
    )

    # Check that source references git-workflow.md or git.md
    source = output["source"].lower()
    assert "git" in source, f"Expected 'git' in source, got: {output['source']}"


def test_agent_uses_list_files_for_wiki_question():
    """Test that agent uses list_files tool when asked about wiki files (Task 2)."""
    result = subprocess.run(
        ["uv", "run", "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, (
        f"Agent exited with code {result.returncode}: {result.stderr}"
    )

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Invalid JSON output: {e}\nStdout: {result.stdout}\nStderr: {result.stderr}"
        )

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must be non-empty"

    assert "source" in output, "Missing 'source' field in output"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Check that list_files was used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "list_files" in tool_names, (
        f"Expected 'list_files' in tool_calls, got: {tool_names}"
    )

    # Check that the list_files result contains wiki files
    list_files_call = next(
        (tc for tc in output["tool_calls"] if tc["tool"] == "list_files"), None
    )
    assert list_files_call is not None, "list_files tool call not found"
    assert "wiki" in list_files_call.get("args", {}).get("path", ""), (
        "list_files should be called with wiki path"
    )


if __name__ == "__main__":
    print("Running Task 1 test...")
    test_agent_outputs_valid_json()
    print("✓ Task 1 test passed")

    print("Running merge conflict test...")
    test_agent_uses_read_file_for_merge_conflict_question()
    print("✓ Merge conflict test passed")

    print("Running wiki files test...")
    test_agent_uses_list_files_for_wiki_question()
    print("✓ Wiki files test passed")

    print("\n✓ All tests passed!")
