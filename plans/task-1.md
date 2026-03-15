# Task 1 Plan: Call an LLM from Code

## LLM Provider and Model

**Provider:** Qwen Code API (self-hosted on VM)
**Model:** `qwen3-coder-plus`

**Reasons:**
- 1000 free requests per day
- Works from Russia without VPN
- OpenAI-compatible API

## Configuration

The agent reads configuration from `.env.agent.secret`:

```
LLM_API_KEY=<my-secret-qwen-key>
LLM_API_BASE=http://<vm-ip>:<qwen-api-port>/v1
LLM_MODEL=qwen3-coder-plus
```

## Agent Architecture

### Input Flow
1. Parse command-line argument (question string)
2. Load environment variables from `.env.agent.secret`
3. Build HTTP request to LLM API

### API Call
- **Endpoint:** `{LLM_API_BASE}/chat/completions`
- **Method:** POST
- **Headers:** 
  - `Content-Type: application/json`
  - `Authorization: Bearer {LLM_API_KEY}`
- **Body:**
  ```json
  {
    "model": "{LLM_MODEL}",
    "messages": [{"role": "user", "content": "<question>"}]
  }
  ```

### Output Flow
1. Parse JSON response from LLM
2. Extract `choices[0].message.content` as the answer
3. Format output as JSON:
   ```json
   {"answer": "<llm-response>", "tool_calls": []}
   ```
4. Print to stdout (only valid JSON)
5. All debug logs go to stderr

## Error Handling

- Missing `.env.agent.secret` → exit with error message to stderr
- Network error → retry logic or exit with error
- Invalid API response → exit with error message to stderr
- Timeout > 60 seconds → exit with error

## Testing Strategy

One regression test:
1. Run `agent.py` with a test question as subprocess
2. Parse stdout as JSON
3. Assert `answer` field exists and is non-empty string
4. Assert `tool_calls` field exists and is empty array

## Files to Create

- `agent.py` — main CLI script
- `AGENT.md` — architecture documentation
- `tests/test_agent.py` — regression test
- `.env.agent.secret` — environment config (gitignored)
