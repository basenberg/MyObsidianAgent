# Obsidian Copilot Setup Guide for Paddy

This guide walks you through connecting the Obsidian Copilot plugin to Paddy so you can query and manage your vault with natural language.

---

## Prerequisites

- **Obsidian** installed with the **Copilot** community plugin enabled
- **Paddy** running (Docker or local uvicorn)
- Your `API_KEY` value from your `.env` file

---

## Step 1: Start Paddy

**Docker (recommended):**
```bash
docker compose up
```

**Local dev server:**
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify Paddy is running:
```bash
curl -s http://localhost:8000/health
```

---

## Step 2: Configure Obsidian Copilot

Open Obsidian → **Settings** → **Copilot** → **Model** tab.

Click **Add Custom Model** and fill in:

| Field | Value |
|---|---|
| **Provider** | `3rd party (openai-format)` |
| **Base URL** | `http://localhost:8000/v1` |
| **API Key** | Value of `API_KEY` in your `.env` (e.g. `your-secret-api-key`) |
| **Model Name** | `paddy` (any string — Paddy ignores it and uses its configured LLM) |

> **Critical:** The Base URL must end with `/v1` — **not** `/v1/chat/completions`.
> The Copilot plugin's OpenAI SDK automatically appends `/chat/completions` to the base URL.
> Using the wrong URL is the most common setup mistake.

Click **Save**, then select the new model as your active Copilot model.

---

## Step 3: Set the API Key

If you left `API_KEY` blank in your `.env`, the Copilot plugin will send `"default-key"` automatically. Paddy will reject it with a 401 unless your `API_KEY` is also set to `"default-key"` (not recommended for production).

For any real deployment, set a unique `API_KEY` in `.env` and configure the same value in the Copilot plugin's **API Key** field.

---

## Step 4: Test the Connection

Open the Copilot chat panel in Obsidian (ribbon icon or `Ctrl+Shift+P` → "Copilot: Open Chat").

Type a message, for example:

> "List the notes in my vault"

You should see Paddy's response streaming in real time. Streaming is enabled by default — each word appears as it is generated.

---

## CORS Notes

Paddy includes the following origins in `ALLOWED_ORIGINS` by default:

- `app://obsidian.md` — Obsidian desktop (Electron)
- `capacitor://localhost` — Obsidian mobile (iOS/Android via Capacitor)

No additional CORS configuration is needed for standard Obsidian desktop/mobile installs. If you are running Paddy behind a reverse proxy, ensure these origins are forwarded correctly.

---

## Troubleshooting

### Response is `401 Unauthorized`

- Confirm the **API Key** in Copilot matches `API_KEY` in your Paddy `.env`.
- If no API key is configured in Copilot, Obsidian sends `"default-key"` — set `API_KEY=default-key` in `.env` for testing only.

### No response / connection refused

- Confirm Paddy is running on port 8000: `curl http://localhost:8000/health`
- Check the Base URL is exactly `http://localhost:8000/v1` (no trailing slash, no `/chat/completions`).

### CORS error in browser console

- Ensure `ALLOWED_ORIGINS` in your `.env` includes `app://obsidian.md` and `capacitor://localhost`.
- The default in-code configuration already includes them; check if a custom `.env` value is overriding it.
- Example correct `.env` entry:
  ```
  ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000","app://obsidian.md","capacitor://localhost"]
  ```

### Streaming stops mid-response

- Check Paddy logs for `agent.llm.streaming_failed` events.
- Confirm `LLM_API_KEY` is valid for your configured `LLM_PROVIDER`.
- Retry the request — transient API errors are the most common cause.

### Wrong model / Paddy uses wrong LLM

- Paddy ignores the model name sent by Copilot. It always uses the model configured in `.env` via `LLM_PROVIDER` and `LLM_MODEL`.
- Update `.env` to change the underlying model, then restart Paddy.

---

## Quick Reference

| Setting | Value |
|---|---|
| Provider type | `3rd party (openai-format)` |
| Base URL | `http://localhost:8000/v1` |
| API Key | Contents of `API_KEY` in `.env` |
| Model Name | `paddy` (or any string) |
| Streaming | Enabled by default — no configuration needed |
| Vault access | Via Docker volume mount at `/vault` — no REST plugin required |
