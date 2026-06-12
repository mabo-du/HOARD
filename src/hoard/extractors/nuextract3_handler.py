"""nuextract3_handler.py — Custom LlamaChatCompletionHandler for NuExtract3.

Extends Llava15ChatHandler to render the GGUF's Jinja2 chat template with
``template=<schema>`` and ``mode="structured"`` — the missing keyword
arguments that unlock NuExtract3's structured extraction mode.

Without this handler, ``create_chat_completion()`` cannot pass the ``template``
variable into the Jinja2 renderer, so the model defaults to content mode
(Markdown OCR) and returns null for all semantic fields.

Usage:
    handler = NuExtract3ChatHandler(clip_model_path, extraction_schema)
    llm = Llama(..., chat_handler=handler)
    response = llm.create_chat_completion(messages=[...])

exports: NuExtract3ChatHandler
used_by: hoard.extractors.nuextract3.NuExtract3Extractor
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, List, Optional, Union

import llama_cpp
from llama_cpp import llama_types
from llama_cpp.llama_chat_format import (
    ImmutableSandboxedEnvironment,
    Llava15ChatHandler,
    _convert_completion_to_chat,
    _get_system_message,
)

logger = logging.getLogger(__name__)


class NuExtract3ChatHandler(Llava15ChatHandler):
    """Custom multimodal chat handler that renders NuExtract3's GGUF chat
    template with the ``template`` variable and ``mode="structured"``.

    This is the architecturally clean solution (Strategy 5 from the research
    paper): it extends Llava15ChatHandler for CLIP/mtmd image processing but
    overrides the text-templating phase to use the GGUF's own Jinja2 template
    with the correct keyword arguments.
    """

    # No hardcoded CHAT_FORMAT — we use the GGUF's tokenizer.chat_template

    def __init__(
        self,
        clip_model_path: str,
        extraction_schema: str | None = None,
        verbose: bool = True,
    ):
        super().__init__(clip_model_path, verbose)
        self.extraction_schema = extraction_schema
        self._gguf_chat_template: str | None = None

    def _get_gguf_template(self, llama: llama_cpp.Llama) -> str:
        """Extract the chat template from the GGUF model metadata."""
        if self._gguf_chat_template is not None:
            return self._gguf_chat_template

        template = llama.metadata.get("tokenizer.chat_template")
        if not template:
            raise ValueError(
                "No tokenizer.chat_template found in GGUF metadata. "
                "This model does not support the NuExtract3 chat format."
            )
        self._gguf_chat_template = template
        return template

    def __call__(
        self,
        *,
        llama: llama_cpp.Llama,
        messages: List[llama_types.ChatCompletionRequestMessage],
        functions: Optional[List[llama_types.ChatCompletionFunction]] = None,
        function_call: Optional[
            llama_types.ChatCompletionRequestFunctionCall
        ] = None,
        tools: Optional[List[llama_types.ChatCompletionTool]] = None,
        tool_choice: Optional[
            llama_types.ChatCompletionToolChoiceOption
        ] = None,
        temperature: float = 0.2,
        top_p: float = 0.95,
        top_k: int = 40,
        min_p: float = 0.05,
        typical_p: float = 1.0,
        stream: bool = False,
        stop: Optional[Union[str, List[str]]] = [],
        seed: Optional[int] = None,
        response_format: Optional[
            llama_types.ChatCompletionRequestResponseFormat
        ] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        repeat_penalty: float = 1.1,
        tfs_z: float = 1.0,
        mirostat_mode: int = 0,
        mirostat_tau: float = 5.0,
        mirostat_eta: float = 0.1,
        model: Optional[str] = None,
        logits_processor: Optional[
            llama_cpp.LogitsProcessorList
        ] = None,
        grammar: Optional[llama_cpp.LlamaGrammar] = None,
        logit_bias: Optional[Dict[str, float]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        **kwargs: Any,
    ) -> Union[
        llama_types.CreateChatCompletionResponse,
        Iterator[llama_types.CreateChatCompletionStreamResponse],
    ]:
        # ── Phase 1: Initialize mtmd context (inherited from Llava15ChatHandler) ──
        self._init_mtmd_context(llama)
        assert self.mtmd_ctx is not None

        # ── Phase 2: Build system message ──
        system_prompt = _get_system_message(messages)
        if system_prompt == "" and self.DEFAULT_SYSTEM_MESSAGE is not None:
            messages = [
                llama_types.ChatCompletionRequestSystemMessage(
                    role="system", content=self.DEFAULT_SYSTEM_MESSAGE
                )
            ] + messages

        # ── Phase 3: Get image URLs before template rendering ──
        # (We need the raw image_url text markers to replace them with
        # mtmd media markers after template rendering)
        image_urls = self.get_image_urls(messages)

        # ── Phase 4: Render using GGUF's NuExtract3 chat template ──
        # This is the key difference from Llava15ChatHandler.
        # We use the GGUF's tokenizer.chat_template (which has the
        # NuExtract3 Jinja2 logic) and pass template + mode kwargs.
        gguf_template_str = self._get_gguf_template(llama)

        # Patch the NuExtract3 GGUF template to render raw image URLs
        # instead of native Qwen3.5 vision tokens (<|vision_start|>...).
        # This lets the mtmd pipeline (from Llava15ChatHandler) find and
        # process the images through CLIP embedding + interleaved evaluation.
        # The template macro uses `item` for the content item variable.
        patched_template = gguf_template_str.replace(
            "{{- '<|vision_start|><|image_pad|><|vision_end|>\\n' }}",
            "{% if item.image_url is mapping %}{{ item.image_url.url }}{% else %}{{ item.image_url }}{% endif %}"
        )

        # Use the same Jinja2 environment as llama-cpp-python's
        # Jinja2ChatFormatter, including the IgnoreGenerationTags extension.
        class IgnoreGenerationTags(  # type: ignore[misc]
            __import__("jinja2").ext.Extension
        ):
            tags = {"generation"}

            def parse(self, parser):
                parser.stream.skip(1)
                return parser.parse_statements(
                    ("name:endgeneration",), drop_needle=True
                )

        # Verify the patch works
        if "vision_start" in patched_template and patched_template.find("<|vision_start|>") > 0:
            logger.warning(
                "Template patch may have failed — image URL might still contain vision tokens"
            )

        template_env = ImmutableSandboxedEnvironment(
            loader=__import__("jinja2").BaseLoader(),
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=[
                IgnoreGenerationTags,
                __import__("jinja2").ext.loopcontrols,
            ],
        ).from_string(patched_template)

        # Get the media marker that mtmd uses for images
        media_marker = self._mtmd_cpp.mtmd_default_marker().decode("utf-8")

        # Render with the structured extraction kwargs
        # The template does:
        #   {%- set mode = mode | default('content') -%}
        #   {%- if template -%}{%- set mode = 'structured' -%}{%- endif -%}
        render_kwargs: dict[str, Any] = {
            "messages": messages,
            "add_generation_prompt": True,
            "eos_token": llama.detokenize([llama.token_eos()]),
            "bos_token": llama.detokenize([llama.token_bos()]),
        }

        if self.extraction_schema:
            render_kwargs["template"] = self.extraction_schema
            render_kwargs["mode"] = "structured"
            render_kwargs["enable_thinking"] = False

        text = template_env.render(**render_kwargs)

        # Replace image URL markers with mtmd media markers
        for image_url in image_urls:
            text = text.replace(image_url, media_marker)

        if self.verbose:
            print(text, file=__import__("sys").stderr)
            logger.debug(f"Rendered prompt ({len(text)} chars)")

        # ── Phase 5: Process images and evaluate ──
        # (identical to Llava15ChatHandler)
        bitmaps = []
        bitmap_cleanup = []
        try:
            for image_url in image_urls:
                image_bytes = self.load_image(image_url)
                bitmap = self._create_bitmap_from_bytes(image_bytes)
                bitmaps.append(bitmap)
                bitmap_cleanup.append(bitmap)

            input_text = self._mtmd_cpp.mtmd_input_text()
            input_text.text = text.encode("utf-8")
            input_text.add_special = True
            input_text.parse_special = True

            chunks = self._mtmd_cpp.mtmd_input_chunks_init()
            if chunks is None:
                raise ValueError("Failed to create input chunks")

            try:
                bitmap_array = (
                    self._mtmd_cpp.mtmd_bitmap_p_ctypes * len(bitmaps)
                )(*bitmaps)
                result = self._mtmd_cpp.mtmd_tokenize(
                    self.mtmd_ctx,
                    chunks,
                    __import__("ctypes").byref(input_text),
                    bitmap_array,
                    len(bitmaps),
                )
                if result != 0:
                    raise ValueError(
                        f"Failed to tokenize input: error code {result}"
                    )

                llama.reset()
                llama._ctx.kv_cache_clear()

                # Import ctypes for the evaluation loop
                import ctypes as _ctypes

                n_chunks = self._mtmd_cpp.mtmd_input_chunks_size(chunks)
                for i in range(n_chunks):
                    chunk = self._mtmd_cpp.mtmd_input_chunks_get(chunks, i)
                    if chunk is None:
                        continue

                    chunk_type = self._mtmd_cpp.mtmd_input_chunk_get_type(chunk)

                    if (
                        chunk_type
                        == self._mtmd_cpp.MTMD_INPUT_CHUNK_TYPE_TEXT
                    ):
                        n_tokens_out = _ctypes.c_size_t()
                        tokens_ptr = (
                            self._mtmd_cpp.mtmd_input_chunk_get_tokens_text(
                                chunk, _ctypes.byref(n_tokens_out)
                            )
                        )
                        if tokens_ptr and n_tokens_out.value > 0:
                            tokens = [
                                tokens_ptr[j]
                                for j in range(n_tokens_out.value)
                            ]
                            if llama.n_tokens + len(tokens) > llama.n_ctx():
                                raise ValueError(
                                    f"Prompt exceeds n_ctx: "
                                    f"{llama.n_tokens + len(tokens)} > {llama.n_ctx()}"
                                )
                            llama.eval(tokens)

                    elif chunk_type in [
                        self._mtmd_cpp.MTMD_INPUT_CHUNK_TYPE_IMAGE,
                        self._mtmd_cpp.MTMD_INPUT_CHUNK_TYPE_AUDIO,
                    ]:
                        chunk_n_tokens = (
                            self._mtmd_cpp.mtmd_input_chunk_get_n_tokens(chunk)
                        )
                        if (
                            llama.n_tokens + chunk_n_tokens
                            > llama.n_ctx()
                        ):
                            raise ValueError(
                                f"Prompt exceeds n_ctx: "
                                f"{llama.n_tokens + chunk_n_tokens} > {llama.n_ctx()}"
                            )

                        new_n_past = llama_cpp.llama_pos(0)
                        result = self._mtmd_cpp.mtmd_helper_eval_chunk_single(
                            self.mtmd_ctx,
                            llama._ctx.ctx,
                            chunk,
                            llama_cpp.llama_pos(llama.n_tokens),
                            llama_cpp.llama_seq_id(0),
                            llama.n_batch,
                            False,
                            _ctypes.byref(new_n_past),
                        )
                        if result != 0:
                            raise ValueError(
                                f"Failed to evaluate chunk: error code {result}"
                            )
                        llama.n_tokens = new_n_past.value

                prompt = llama.input_ids[: llama.n_tokens].tolist()

            finally:
                self._mtmd_cpp.mtmd_input_chunks_free(chunks)

        finally:
            for bitmap in bitmap_cleanup:
                self._mtmd_cpp.mtmd_bitmap_free(bitmap)

        # ── Phase 6: Generate completion ──
        if response_format is not None and response_format["type"] == "json_object":
            from llama_cpp.llama_chat_format import _grammar_for_response_format

            grammar = _grammar_for_response_format(response_format)

        # Tool handling (same as base class)
        if functions is not None:
            tools = [
                {"type": "function", "function": function}
                for function in functions
            ]
        if function_call is not None:
            if isinstance(function_call, str) and function_call in (
                "none",
                "auto",
            ):
                tool_choice = function_call
            if isinstance(function_call, dict) and "name" in function_call:
                tool_choice = {
                    "type": "function",
                    "function": {"name": function_call["name"]},
                }

        tool = None
        if (
            tool_choice is not None
            and isinstance(tool_choice, dict)
            and tools is not None
        ):
            name = tool_choice["function"]["name"]
            tool = next(
                (t for t in tools if t["function"]["name"] == name), None
            )
            if tool is None:
                raise ValueError(
                    f"Tool choice '{name}' not found in tools."
                )
            schema = tool["function"]["parameters"]
            try:
                grammar = llama_cpp.LlamaGrammar.from_json_schema(
                    json.dumps(schema), verbose=llama.verbose
                )
            except Exception as e:
                if llama.verbose:
                    print(str(e), file=__import__("sys").stderr)
                grammar = llama_cpp.LlamaGrammar.from_string(
                    llama_cpp.JSON_GBNF, verbose=llama.verbose  # type: ignore[attr-defined]
                )

        completion_or_chunks = llama.create_completion(
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
            typical_p=typical_p,
            logprobs=top_logprobs if logprobs else None,
            stream=stream,
            stop=stop,
            seed=seed,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            repeat_penalty=repeat_penalty,
            tfs_z=tfs_z,
            mirostat_mode=mirostat_mode,
            mirostat_tau=mirostat_tau,
            mirostat_eta=mirostat_eta,
            model=model,
            logits_processor=logits_processor,
            grammar=grammar,
            logit_bias=logit_bias,  # type: ignore[arg-type]
        )

        if tool is not None:
            from llama_cpp.llama_chat_format import _convert_completion_to_chat_function

            tool_name = tool["function"]["name"]
            return _convert_completion_to_chat_function(
                tool_name, completion_or_chunks, stream
            )
        return _convert_completion_to_chat(completion_or_chunks, stream=stream)
