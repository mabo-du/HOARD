"""providers — Multi-provider AI abstraction layer (Phase B).

Provides a capability-aware ModelProvider protocol that routes inference
requests across local (Ollama) and cloud (OpenAI, Anthropic, Google) backends,
with hardware-tier auto-detection, encrypted credential management, privacy
tiers, and per-request cost tracking.

Usage:
    from hoard.providers import get_router
    from hoard.providers.protocol import InferenceRequest

    router = get_router()
    request = InferenceRequest(
        messages=[{"role": "user", "content": "Summarise the stratigraphy"}],
        model_name="qwen3.5-4b",
    )
    response = await router.route(request, phase=3)

Architecture (see docs/research-prompts/multi-provider-ai-abstraction.md):
    ModelProvider protocol  ←  OllamaProvider, OpenAIProvider, ...
         ↑                          ↑
    ProviderRouter         uses  CredentialStore
         ↑                          ↑
    HardwareProfile        uses  ~/.config/hoard/credentials.yaml.enc
"""

from hoard.providers.router import ProviderRouter, ProviderSelection, get_router
from hoard.providers.protocol import (
    ModelProvider,
    ProviderCapabilities,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
)
from hoard.providers.ollama import OllamaProvider
from hoard.providers.openai import OpenAIProvider
from hoard.providers.anthropic import AnthropicProvider
from hoard.providers.google import GoogleProvider
from hoard.providers.credentials import CredentialStore
from hoard.providers.hardware import (
    HardwareProfile,
    ModelTier,
    detect_hardware,
    suggest_tier,
)

__all__ = [
    "ProviderRouter",
    "ProviderSelection",
    "get_router",
    "ModelProvider",
    "ProviderCapabilities",
    "InferenceRequest",
    "InferenceResponse",
    "TokenUsage",
    "OllamaProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "CredentialStore",
    "HardwareProfile",
    "ModelTier",
    "detect_hardware",
    "suggest_tier",
]
