# Google Gemini Models (2026)

**CRITICAL RULE:** Do NOT blindly change or downgrade models in the codebase (e.g., in `insight_pipeline.py` or `slip_parser.py`) without reading this document first. In the past, agents have mistakenly downgraded futuristic models to deprecated ones (like `gemini-1.5-flash`), causing production outages.

## Available Models
Based on our API rate limits and availability, the following models are verified to work:

- `gemini-3.7-flash`
- `gemini-3.6-flash`
- `gemini-3.5-flash`
- `gemini-3.5-flash-lite`
- `gemini-3.1-flash-lite`
- `gemini-3-flash-preview`
- `gemini-3-flash`
- `gemini-2.5-flash-lite`
- `gemini-2.5-flash`

## Fallback Configuration (LLMCaller)
Our `PipelineConfig` manages the fallback order.
- If a model throws a `404 Not Found` or `429 Too Many Requests` (e.g. rate limit 6/5 RPM hit), the `LLMCaller` will automatically fallback to the next model in the list.
- **NEVER** remove futuristic models just because you think they don't exist. They DO exist in our environment.

