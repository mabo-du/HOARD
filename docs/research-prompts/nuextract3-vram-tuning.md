# NuExtract3 VRAM Budget — Final Tuning

## Status
NuExtract3ChatHandler (custom Llava15ChatHandler) is built and working:
- ✅ GGUF Jinja2 template rendered with template=<schema> + mode="structured"
- ✅ Image URL patch for mtmd compatibility
- ✅ mtmd processes image (nx=39, ny=55 tokens)
- ❌ OOM during "encoding image slice..." (4.7 GB allocation)

## The VRAM Budget
RTX 3070 Laptop: 8 GB total
- Model weights (Q4_K_M): ~2.7 GB
- KV cache (n_ctx=16384): ~512 MB
- Vulkan backend overhead: varies
- mtmd image encoding: tries to allocate 4.7 GB
- Total demand: ~8 GB + — exceeds budget

## Solutions to Test
1. **Reduce n_ctx** — 16384→4096 saves ~1.5 GB KV cache
2. **Offload fewer layers** — 33→24 layers on GPU saves ~700 MB
3. **Reduce image resolution** — MAX_IMAGE_DIMENSION 2048→1024 saves CLIP memory
4. **Use --no-warmup or lazy GPU allocation** — avoid double-buffering
5. **Try CUDA backend** instead of Vulkan (better memory management on NVIDIA)
