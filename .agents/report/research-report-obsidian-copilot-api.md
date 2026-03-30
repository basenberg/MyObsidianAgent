# Obsidian Copilot OpenAI-Compatible API Integration — Source Code Research Report

**Source:** `logancyang/obsidian-copilot` master branch + `pydantic/pydantic-ai` main branch
**Date:** 2026-03-28

---

## Repository Structure — `src/LLMProviders/`

```
src/LLMProviders/
├── ChatOpenRouter.ts          ← Primary class for OPENROUTERAI, LM_STUDIO, COPILOT_PLUS
├── ChatLMStudio.ts            ← LM Studio subclass
├── chatModelManager.ts        ← Provider config builder; OPENAI_FORMAT uses ChatOpenAI directly
├── chainRunner/
│   └── LLMChainRunner.ts      ← Where .stream() is actually called
└── CustomOpenAIEmbeddings.ts
```

**Key insight:** `OPENAI_FORMAT` (Paddy's target provider type) uses plain `ChatOpenAI` from `@langchain/openai`, NOT `ChatOpenRouter`. The other custom providers (LM_STUDIO, OPENROUTERAI, COPILOT_PLUS) use `ChatOpenRouter extends ChatOpenAI`.

---

## 1. Provider Enum

From `src/constants.ts`:

```typescript
export enum ChatModelProviders {
  OPENAI = "openai",
  AZURE_OPENAI = "azure openai",
  ANTHROPIC = "anthropic",
  OPENROUTERAI = "openrouterai",
  OLLAMA = "ollama",
  LM_STUDIO = "lm studio",
  OPENAI_FORMAT = "3rd party (openai-format)",  // ← Paddy's target
  COPILOT_PLUS = "copilot plus",
  // ...
}
```

The `ProviderInfo` metadata for `OPENAI_FORMAT`:

```typescript
[ChatModelProviders.OPENAI_FORMAT]: {
  label: "OpenAI Format",
  host: "https://api.example.com/v1",         // documentation placeholder only
  curlBaseURL: "https://api.example.com/v1",
  keyManagementURL: "",
  listModelURL: "",
},
```

---

## 2. Endpoint URL Construction

### The exact provider config block for `OPENAI_FORMAT` (from `chatModelManager.ts`):

```typescript
[ChatModelProviders.OPENAI_FORMAT]: {
  modelName: modelName,
  apiKey: await getDecryptedKey(customModel.apiKey || settings.openAIApiKey),
  streamUsage: customModel.streamUsage ?? false,
  configuration: {
    baseURL: customModel.baseUrl,           // ← exact user-configured URL, no modification
    fetch: customModel.enableCors ? safeFetch : undefined,
    defaultHeaders: { "dangerously-allow-browser": "true" },
  },
  ...this.getOpenAISpecialConfig(
    modelName,
    customModel.maxTokens ?? settings.maxTokens,
    customModel.temperature ?? settings.temperature,
    customModel
  ),
},
```

This config is passed to `ChatOpenAI`, which internally constructs:

```typescript
new OpenAI({
  apiKey: fields.apiKey,
  baseURL: fields.configuration?.baseURL,  // e.g., "http://localhost:8000/v1"
  ...
})
```

**The OpenAI SDK automatically appends `/chat/completions` to the baseURL.**

### Final URL math:
```
User configures:   http://localhost:8000/v1
SDK appends:       /chat/completions
Final call target: http://localhost:8000/v1/chat/completions
```

### Azure strips the suffix (NOT applied to OPENAI_FORMAT):
```typescript
// normalizeAzureUrl() — Azure-only, does NOT apply to OPENAI_FORMAT
baseUrl = baseUrl.replace(/\/(chat\/completions|embeddings)$/, "");
```

### LM Studio default confirms the `/v1` pattern:
```typescript
[ChatModelProviders.LM_STUDIO]: {
  configuration: {
    baseURL: customModel.baseUrl || "http://localhost:1234/v1",
    // ...
  },
},
```

**User instruction:** Enter `http://localhost:8000/v1` (not `http://localhost:8000`) in Copilot's base URL field.

---

## 3. Authentication

### For `OPENAI_FORMAT`:

```typescript
apiKey: await getDecryptedKey(customModel.apiKey || settings.openAIApiKey),
```

Sent as standard `Authorization: Bearer <apiKey>` header by the OpenAI SDK.

### Default key when none configured:

```typescript
[ChatModelProviders.OPENAI_FORMAT]: () => "default-key",
[ChatModelProviders.LM_STUDIO]: () => "default-key",
[ChatModelProviders.OLLAMA]: () => "default-key",
```

**If the user does not configure an API key for `OPENAI_FORMAT`, the literal string `"default-key"` is sent.** Paddy must handle this.

### Extra headers sent:

```typescript
defaultHeaders: { "dangerously-allow-browser": "true" }
```

Paddy can safely ignore this header.

---

## 4. Request Body

### Base streaming config (applies to ALL providers):

```typescript
const baseConfig = {
  modelName: modelName,
  streaming: customModel.stream ?? true,   // ← streaming = TRUE by default
  maxRetries: 3,
  maxConcurrency: 3,
  temperature: resolvedTemperature,        // default: 0.1
};
```

From `src/constants.ts`:

```typescript
export const DEFAULT_MODEL_SETTING = {
  MAX_TOKENS: 6000,
  TEMPERATURE: 0.1,
  REASONING_EFFORT: ReasoningEffort.LOW,
  VERBOSITY: Verbosity.MEDIUM,
} as const;
```

### Wire format of the actual HTTP request body:

```json
{
  "model": "<user-configured model name>",
  "messages": [
    { "role": "system", "content": "<system prompt>" },
    { "role": "user", "content": "<prior turn>" },
    { "role": "assistant", "content": "<prior response>" },
    { "role": "user", "content": "<current message>" }
  ],
  "stream": true,
  "temperature": 0.1,
  "max_tokens": 6000,
  "stream_options": { "include_usage": true }
}
```

**`stream: true` is the default.** Paddy MUST support SSE streaming.

---

## 5. Message Content Format

### Text-only (standard case):

```typescript
messages.push({ role: "system", content: "<system prompt string>" });
messages.push({ role: "user", content: "<plain text string>" });
messages.push({ role: "assistant", content: "<plain text string>" });
```

### Multimodal (images present):

```typescript
messages.push({
  role: "user",
  content: [
    { type: "text", text: "<envelope text>" },
    { type: "image_url", image_url: { url: "..." } },
  ],
});
```

**For Paddy MVP:** `content` will always be a plain string. Structured array content only appears when users attach images in the Copilot chat UI.

---

## 6. Delta Content Extraction — `extractDeltaContent`

Full verbatim code from `src/LLMProviders/ChatOpenRouter.ts`:

```typescript
/**
 * Flatten OpenRouter delta content into a single text string.
 *
 * @param content Delta content payload
 * @returns Text representation for downstream streaming
 */
private extractDeltaContent(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }

  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") {
          return part;
        }
        if (part && typeof part === "object" && typeof part.text === "string") {
          return part.text;
        }
        return "";
      })
      .join("");
  }

  return "";
}
```

**Implication for Paddy:** The plugin handles both `string` and `[{type, text}]` delta content. Use plain strings — simplest and fully supported.

---

## 7. SSE Streaming Response Format

The plugin reads `choices[0].delta.content` from each chunk:

```typescript
for await (const rawChunk of stream as AsyncIterable<OpenRouterChatChunk>) {
  const choice = rawChunk.choices?.[0];
  const delta = choice?.delta;
  if (!choice || !delta) continue;

  const content = this.extractDeltaContent(delta.content);
  // ...
}
```

### Expected SSE wire format from Paddy:

```
data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

---

## 8. The Streaming Call Site

From `LLMChainRunner.ts`:

```typescript
const chatStream = await withSuppressedTokenWarnings(() =>
  this.chainManager.chatModelManager.getChatModel().stream(messages, {
    signal: abortController.signal,
  })
);

for await (const chunk of chatStream) {
  if (abortController.signal.aborted) break;
  streamer.processChunk(chunk);
}
```

This is LangChain's `.stream()` which calls `chat.completions.create({ stream: true, ... })` internally.

---

## 9. Pydantic AI — Streaming Implementation

### `run_stream` signature:

```python
@asynccontextmanager
async def run_stream(
    self,
    user_prompt: str | Sequence[UserContent] | None = None,
    *,
    message_history: Sequence[ModelMessage] | None = None,
    model: Model | KnownModelName | str | None = None,
    deps: AgentDepsT = None,
    # ...
) -> AsyncIterator[StreamedRunResult[AgentDepsT, Any]]: ...
```

### Usage pattern for Paddy's SSE endpoint:

```python
from fastapi.responses import StreamingResponse
import json, time, uuid

async def stream_response(user_prompt: str, history: list, deps: AgentDependencies):
    async def generate():
        async with vault_agent.run_stream(
            user_prompt, deps=deps, message_history=history
        ) as result:
            async for chunk in result.stream_text(delta=True):
                data = {
                    "id": f"chatcmpl-{uuid.uuid4()}",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(data)}\n\n"
            # Final chunk
            yield f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### `stream_text` method:

```python
async def stream_text(
    self,
    *,
    delta: bool = False,        # True = yield each new chunk; False = yield full accumulated text
    debounce_by: float | None = 0.1,
) -> AsyncIterator[str]: ...
```

Use `delta=True` for SSE streaming to avoid re-sending the full accumulated text on every chunk.

---

## 10. Non-Streaming Response Format (fallback)

If a user explicitly configures `stream: false` on their Copilot model:

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "paddy",
  "choices": [{
    "index": 0,
    "message": { "role": "assistant", "content": "<full response>" },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  }
}
```

Paddy's current `ChatResponse` model already handles this case correctly.

---

## 11. Summary — Implementation Requirements for Paddy

| Concern | Requirement |
|---|---|
| **Streaming** | MUST support SSE (`stream: true` is default). Use `agent.run_stream()` + `StreamingResponse`. |
| **Base URL config** | User enters `http://localhost:8000/v1`. Paddy exposes `POST /v1/chat/completions`. |
| **Auth** | Accept `Authorization: Bearer <any-string>`. If no user key, `"default-key"` is sent. |
| **`model` field** | Accept any string — ignore it or use it to route LLM selection. |
| **`stream` field in ChatRequest** | Must accept `True` without error (currently hardcoded `False`). |
| **`content` field** | Plain `str` for text-only. Accept `str | list` for multimodal future-proofing. |
| **SSE format** | `data: {...}\n\n` chunks, `choices[0].delta.content` string, ends with `data: [DONE]\n\n`. |
| **Temperature / max_tokens** | Sent in request body. Paddy can accept and optionally forward to its LLM. |
| **Extra header** | `dangerously-allow-browser: true` — safe to ignore. |

### Pydantic model changes needed:

```python
class ChatMessage(BaseModel):
    role: str
    content: str | list  # Accept both plain strings and structured arrays

class ChatRequest(BaseModel):
    model: str = "paddy"
    messages: list[ChatMessage]
    stream: bool = True          # Change default to True
    temperature: float | None = None
    max_tokens: int | None = None
```
