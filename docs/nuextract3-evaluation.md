# NuExtract3 — Phase 1 v1.1 Evaluation

## Model Overview

| Parameter | Value |
|-----------|-------|
| Model | `numind/NuExtract3` |
| Base | Qwen3.5-4B |
| Size | 4B params, BF16 |
| License | Apache 2.0 |
| HF Downloads | 17,501/month |

## Structured Extraction Benchmark (vs HOARD-relevant competitors)

| Model | Average Score | Failed JSON (%) |
|-------|-------------|-----------------|
| **NuExtract3-4B** | **0.651** | 2.7% |
| gemma-4-E4B-it | 0.538 | 3.1% |
| Qwen3.5-9B | 0.479 | 17% |
| Qwen3.5-4B | 0.417 | 23% |
| GLM-4.6V-Flash | 0.435 | 15% |

NuExtract3 achieves a **56% improvement** over the base Qwen3.5-4B and significantly
outperforms GLM-4.6V-Flash (the closest model to our current GLM-OCR).

## Key Features

- **Typed JSON templates**: verbatim-string, integer, date, enum, currency, etc.
  — perfect for context sheet fields like context_number, period, quantity, description
- **Reasoning mode**: optional thinking for difficult documents (ambiguous handwriting,
  complex layouts)
- **Markdown conversion**: can extract document content as clean Markdown
- **vLLM deployment**: OpenAI-compatible API, easy integration
- **Transformers support**: `AutoModelForImageTextToText` from transformers 5.x

## Relevance to HOARD Phase 1

NuExtract3 could replace GLM-OCR for context sheet extraction with:

1. **Better accuracy** (56% improvement on structured benchmarks)
2. **Schema-constrained output** via JSON templates — no checkbox post-processor needed!
3. **Type-aware extraction** — can directly output integers for qty, dates for period, enums for context type
4. **Markdown mode** — could serve as an alternative to Docling for finds catalogues

## Deployment Challenges

- **Not available on Ollama** — needs separate vLLM server or transformers direct load
- **VRAM at BF16**: ~8 GB (full precision) — would need 4-bit quantisation (~2-3 GB)
- **vLLM**: `vllm serve numind/NuExtract3` runs alongside Ollama
- **Transformers**: `AutoModelForImageTextToText.from_pretrained()` — simpler but less efficient

## Recommendation

**Adopt for v1.1** as the primary Phase 1 extraction model. For v1.0, GLM-OCR (2.2 GB,
Ollama, already deployed) is adequate. The migration path:

1. Pull NuExtract3 GGUF quant if/when available on Ollama (simplest integration)
2. Or add a vLLM-based extraction path alongside the existing Ollama path
3. Map HOARD's Pydantic ContextSheet schema to NuExtract's JSON template format
4. Remove checkbox post-processor (NuExtract3 handles enum fields natively)

NuExtract3's template system maps cleanly to our ContextSheet Pydantic model:

```python
# Pydantic ContextSheet
context_sheet_schema = {
    "context_number": "verbatim-string",
    "type": ["layer", "cut", "deposit", "fill", "structure"],
    "period": ["palaeolithic", "mesolithic", "neolithic", "bronze age",
               "iron age", "roman", "anglo-saxon", "medieval",
               "post-medieval", "modern", "undated"],
    "description": "string",
    "interpretation": "string",
    "cut_by": ["string"],
    "cuts": ["string"],
    "same_as": "verbatim-string",
    "sketch_present": ["yes", "no"],
    "finds": [{"type": "string", "qty": "integer", "period": "string", "notes": "string"}],
    "samples": [{"id": "verbatim-string", "type": "string", "notes": "string"}],
}
```
