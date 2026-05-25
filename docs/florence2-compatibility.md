# Florence-2 Compatibility with Transformers 5.9

Florence-2-large (`microsoft/Florence-2-large`) has compatibility issues with
transformers >= 5.x. The model's custom `configuration_florence2.py` accesses
`forced_bos_token_id` before it's set as an attribute on `Florence2LanguageConfig`.

## Error

```
'Florence2LanguageConfig' object has no attribute 'forced_bos_token_id'
```

This occurs during `__init__` of `Florence2LanguageConfig` at line 265 of the
cached config file.

## Fix

Patch the cached `configuration_florence2.py` to add attribute defaults
before the access. The file is at:

```
~/.cache/huggingface/modules/transformers_modules/microsoft/Florence_hyphen_2_hyphen_large/
  21a599d414c4d928c9032694c424fb94458e3594/configuration_florence2.py
```

In `Florence2LanguageConfig.__init__`, **before** line 265:

```python
if self.forced_bos_token_id is None and kwargs.get("force_bos_token_to_be_generated", False):
```

Insert:

```python
if not hasattr(self, 'forced_bos_token_id') or self.forced_bos_token_id is None:
    self.forced_bos_token_id = getattr(self, 'bos_token_id', None)
if not hasattr(self, 'forced_eos_token_id') or self.forced_eos_token_id is None:
    self.forced_eos_token_id = getattr(self, 'eos_token_id', None)
```

## Alternative: Pin transformers version

```bash
pip install transformers==4.45.2
```

This resolves the issue but may break compatibility with other models requiring
newer transformers features.

## Why Florence-2 was removed from HOARD

Beyond the `forced_bos_token_id` issue, Florence-2 also triggers a second
error with transformers 5.9:

```
'Florence2ForConditionalGeneration' object has no attribute '_supports_sdpa'
```

These cascade failures, combined with Florence-2's ~1.5 GB download and the
availability of Qwen3-VL-8B (already downloaded and working), made it pragmatic
to remove Florence-2 entirely from the Phase 2 pipeline. Phase 2 now uses
Qwen3-VL-8B or GLM-OCR exclusively.

If Florence-2 bounding box extraction is desired in a future version, either:
1. Pin transformers to 4.45.x
2. Use the patched config file approach above
3. Wait for upstream fixes from Microsoft or HuggingFace
