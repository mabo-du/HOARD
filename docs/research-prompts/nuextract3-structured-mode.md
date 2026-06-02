# NuExtract3 Structured Extraction — Remaining Issue

## Context

NuExtract3 Q4_K_M GGUF is loaded via `llama-cpp-python` v0.3.24 with Vulkan GPU backend (RTX 3070, all 33 layers). The model:
- Loads correctly with mmproj for vision ✅
- Processes images via `create_chat_completion` with `image_url` ✅
- Outputs structured JSON matching the ContextSheet schema ✅
- Correctly identifies the context number ([47003]) from the image ✅
- **But all content fields (type, description, interpretation, period, sketch_present) are null** ❌

## The Problem

The GGUF's built-in chat template (a Jinja2 template stored in metadata) supports `template`, `mode`, and `enable_thinking` kwargs. When `template` is set, `mode` becomes `"structured"`, and the model performs proper structured extraction.

`llama-cpp-python` v0.3.24's `create_chat_completion()` has an explicit parameter list — no `**kwargs` — so it **cannot forward `template` to the Jinja renderer**.

Embedding the template markers (`【task】structured extraction`, `【template_start】...`, `【document_start】...`) in the message text gives partial results (correct JSON structure, null content).

## The GGUF Chat Template
The template is stored at `tokenizer.chat_template` in the GGUF metadata. Key logic:
```
{%- set mode = mode | default('content') -%}
{%- if template -%}{%- set mode = 'structured' -%}{%- endif -%}
```
When `template` is a non-empty Jinja variable, mode switches to `structured` and the template is rendered properly. Without this, the model defaults to `content` mode (markdown/conversion).

## What We've Tried

| Approach | Result |
|----------|--------|
| Ollama `/api/generate` | 500 error — model can't load with Ollama's template engine |
| Ollama `/api/chat` | Empty output — no chat_template_kwargs support |
| `llama-cpp-python` `create_chat_completion` with marker text | Partial JSON — structure correct, content null |
| `llama-cpp-python` `create_completion` with manual prompt | Can't handle multimodal images |
| `llama-server` (system binary) | ROCm only — doesn't see NVIDIA GPU |
| `create_chat_completion_openai_v1` | Passes through to same handler, same limitation |

## Potential Solutions to Research

1. **Register a custom `chat_format` handler** — `llama_cpp.llama_chat_format.register_chat_format("nuextract3")` accepts a function with `**kwargs`. A custom handler can:
   - Extract the GGUF's Jinja template
   - Render it with `template=<context_sheet_template>` and `mode="structured"` using Python `jinja2`
   - Return the rendered prompt as a `ChatFormatterResponse`
   - This keeps multimodal image handling intact (the handler receives raw messages with `image_url`)

2. **Write a custom `chat_handler`** — `Llama(chat_handler=my_handler)` accepts a callable. Same approach as above.

3. **Use the `llama_cpp.llama_chat_format.hf_tokenizer_config_to_chat_formatter` function** — It returns a formatter that accepts `**kwargs`. The formatter is already available but unused because `create_chat_completion` doesn't pass kwargs through.

4. **Monkey-patch** `create_chat_completion` to forward `**kwargs` to the handler — fragile but simple.

5. **Use the `numind` Python SDK** (`pip install numind`) — Has `NuExtract` class that handles the template properly via transformers.

## Relevant Code Locations

- `src/hoard/extractors/nuextract3.py` — current extractor implementation
- `src/hoard/extractors/template.py` — Pydantic → NuExtract3 template converter
- GGUF model: `~/.cache/huggingface/hub/models--numind--NuExtract3-GGUF/snapshots/631a32f126925ea54d031dc1cb23c9208889c529/NuExtract3-Q4_K_M.gguf`
- Test image: Pinn Brook page 4 at `erd_workspace/pinnbrook/assets/..._page_004.png`
- GLM-OCR successfully extracts this page (context 47003, Limestone Deposit, Topsoil)

## Test Command
```python
from llama_cpp import Llama
llm = Llama(model_path=model_path, mmproj=mmproj_path, n_gpu_layers=-1, n_ctx=16384, verbose=False)
# Need to pass template=template_json_str, mode="structured" to the Jinja renderer
```
