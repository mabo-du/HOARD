"""router.py — Provider selection and routing logic.

Implements three routing modes:
- Manual: user-specified provider per phase (strict adherence)
- Auto: cascading availability with hardware-aware fallback
- Quality: hybrid — local for extraction phases, cloud for synthesis

Also manages privacy tiers, audit logging, and cost tracking.

exports: ProviderRouter, ProviderSelection, get_router
used_by: hoard.phases.* (planned for Phase B integration)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from hoard.providers.protocol import (
    InferenceRequest,
    InferenceResponse,
    ModelProvider,
    ProviderCapabilities,
    TokenUsage,
    PrivacyTier,
    ProviderError,
    AuthenticationError,
    RateLimitError,
)
from hoard.providers.credentials import CredentialStore
from hoard.providers.hardware import (
    HardwareProfile,
    ModelTier,
    TIER_DEFINITIONS,
    detect_hardware,
    suggest_tier,
)
from hoard.providers.ollama import OllamaProvider
from hoard.providers.openai import OpenAIProvider
from hoard.providers.anthropic import AnthropicProvider
from hoard.providers.google import GoogleProvider


class RoutingMode(str, Enum):
    """How the router selects which provider to use."""

    MANUAL = "manual"  # User-specified per-phase providers only
    AUTO = "auto"  # Cascading availability with fallback
    QUALITY = "quality"  # Hybrid: local for extraction, cloud for synthesis


@dataclass
class ProviderSelection:
    """A configured provider choice for a single phase."""

    provider_name: str  # "ollama", "openai", "anthropic", "google"
    model_name: str
    profile: str = "default"


@dataclass
class RoutingConfig:
    """Complete provider routing configuration for a project session."""

    mode: RoutingMode = RoutingMode.AUTO
    privacy_tier: PrivacyTier = PrivacyTier.STRICT_LOCAL
    hardware_tier: ModelTier | None = None  # None = auto-detect

    # Per-phase manual overrides (only used in MANUAL mode)
    phase_providers: dict[int, ProviderSelection] = field(default_factory=dict)

    # Fallback chain per phase (used in AUTO/QUALITY mode)
    fallback_chain: dict[int, list[ProviderSelection]] = field(default_factory=dict)

    # Quality mode: which phases prefer cloud
    cloud_preferred_phases: set[int] = field(default_factory=lambda: {3, 4})

    # Budgets
    latency_budget_seconds: int = 60


# ── Audit Log Entry ──────────────────────────────────────────────────────────


@dataclass
class AuditEntry:
    """A single inference request record for the project audit trail."""

    phase: int
    provider: str
    model: str
    timestamp: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    privacy_tier: str
    success: bool
    error: str = ""


# ── Router ───────────────────────────────────────────────────────────────────


class ProviderRouter:
    """Routes inference requests to the optimal provider based on config.

    This is the main entry point for all model inference in HOARD.
    Phase modules should call router.route() instead of calling Ollama directly.

    Args:
        config_path: Path to TOML configuration file
                     (~/.config/hoard/config.yaml).
        project_id: Current project ID (for audit log scoping).
    """

    def __init__(
        self,
        config_path: Path | None = None,
        project_id: str = "",
    ) -> None:
        self.config_path = config_path or Path.home() / ".config" / "hoard" / "config.yaml"
        self.project_id = project_id
        self._config: RoutingConfig | None = None
        self._credential_store: CredentialStore | None = None
        self._hardware_profile: HardwareProfile | None = None
        self._audit_log: list[AuditEntry] = []
        self._initialised = False

    # ── Initialisation ───────────────────────────────────────────────────

    def initialise(self, interactive: bool = False) -> str:
        """Detect hardware, load config, suggest tier.

        Should be called once at the start of a session.

        Args:
            interactive: If True, format output for user prompt (init wizard).

        Returns:
            Human-readable summary string.
        """
        self._hardware_profile = detect_hardware()
        self._credential_store = CredentialStore()
        self._config = self._load_or_default()
        self._initialised = True

        tier, explanation = suggest_tier(self._hardware_profile)
        if self._config.hardware_tier is None:
            self._config.hardware_tier = tier

        if interactive:
            from hoard.providers.hardware import format_tier_summary
            return format_tier_summary(self._hardware_profile, tier) + f"\n  {explanation}"
        return f"Router initialised: {tier.value} tier | {explanation}"

    @property
    def hardware_profile(self) -> HardwareProfile | None:
        return self._hardware_profile

    @property
    def audit_log(self) -> list[AuditEntry]:
        return list(self._audit_log)

    # ── Core Routing ─────────────────────────────────────────────────────

    async def route(self, request: InferenceRequest, phase: int) -> InferenceResponse:
        """Route an inference request to the optimal provider.

        Args:
            request: Normalised inference request.
            phase: HOARD phase number (0-5) — affects provider selection.

        Returns:
            Normalised inference response.

        Raises:
            ProviderError: If all providers in the chain fail.
            AuthenticationError: If credentials are invalid.
        """
        if not self._initialised:
            raise RuntimeError("ProviderRouter not initialised. Call .initialise() first.")

        config = self._config
        if config is None:
            raise RuntimeError("No routing configuration loaded.")

        # Build the provider chain to try
        chain = self._build_chain(phase, request)

        last_error: Exception | None = None
        for selection in chain:
            try:
                provider = self._instantiate(selection)
                response = await provider.generate(request)
                self._audit(
                    phase=phase,
                    provider=selection.provider_name,
                    model=selection.model_name,
                    usage=response.usage,
                    success=True,
                )
                return response
            except AuthenticationError as e:
                self._audit(
                    phase=phase,
                    provider=selection.provider_name,
                    model=selection.model_name,
                    usage=TokenUsage(),
                    success=False,
                    error=str(e),
                )
                raise  # Don't fallback on auth errors — re-entering the same key won't help
            except RateLimitError as e:
                self._audit(
                    phase=phase,
                    provider=selection.provider_name,
                    model=selection.model_name,
                    usage=TokenUsage(),
                    success=False,
                    error=str(e),
                )
                last_error = e
                continue  # Try next in chain
            except ProviderError as e:
                self._audit(
                    phase=phase,
                    provider=selection.provider_name,
                    model=selection.model_name,
                    usage=TokenUsage(),
                    success=False,
                    error=str(e),
                )
                last_error = e
                continue  # Try next in chain

        # All providers in the chain failed
        raise ProviderError(
            f"All providers failed for phase {phase}. Last error: {last_error}",
        )

    def _build_chain(
        self, phase: int, request: InferenceRequest,
    ) -> list[ProviderSelection]:
        """Build the ordered list of providers to try for a request."""
        config = self._config
        assert config is not None

        if config.mode == RoutingMode.MANUAL:
            # Strict — only the configured provider
            sel = config.phase_providers.get(phase)
            if sel:
                return [sel]
            # Fallback to tier default
            return self._tier_chain(phase)

        elif config.mode == RoutingMode.QUALITY:
            # Hybrid: use cloud for prose phases, local for extraction
            if phase in config.cloud_preferred_phases:
                cloud_chain = self._cloud_chain(phase)
                local_chain = self._tier_chain(phase)
                return cloud_chain + local_chain  # Cloud first, local fallback
            else:
                local_chain = self._tier_chain(phase)
                cloud_chain = self._cloud_chain(phase) if config.privacy_tier != PrivacyTier.STRICT_LOCAL else []
                return local_chain + cloud_chain

        else:  # AUTO mode
            local_chain = self._tier_chain(phase)
            cloud_chain = self._cloud_chain(phase)
            return local_chain + cloud_chain

    def _tier_chain(self, phase: int) -> list[ProviderSelection]:
        """Build provider chain from the hardware tier definition."""
        config = self._config
        assert config is not None
        tier = config.hardware_tier or ModelTier.BUDGET
        phase_config = TIER_DEFINITIONS.get(tier, {}).get(phase)
        if phase_config:
            return [ProviderSelection(
                provider_name=phase_config["provider"],
                model_name=phase_config["model"],
            )]
        return []

    def _cloud_chain(self, phase: int) -> list[ProviderSelection]:
        """Build cloud fallback chain based on phase."""
        # Generic cloud chain — prefers cheapest capable model
        chains: dict[int, list[ProviderSelection]] = {
            1: [
                ProviderSelection("google", "gemini-2.5-flash-lite"),
                ProviderSelection("openai", "gpt-4o-mini"),
            ],
            2: [
                ProviderSelection("google", "gemini-2.5-flash"),
                ProviderSelection("openai", "gpt-4o-mini"),
            ],
            3: [
                ProviderSelection("anthropic", "claude-sonnet-4-20250514"),
                ProviderSelection("google", "gemini-2.5-flash"),
                ProviderSelection("openai", "gpt-4o-mini"),
            ],
            4: [
                ProviderSelection("google", "gemini-2.5-flash-lite"),
                ProviderSelection("openai", "gpt-4o-mini"),
            ],
        }
        return chains.get(phase, [])

    # ── Provider Factory ─────────────────────────────────────────────────

    def _instantiate(self, selection: ProviderSelection) -> ModelProvider:
        """Create a provider instance from a selection descriptor."""
        provider = selection.provider_name
        model = selection.model_name

        if provider == "ollama":
            return OllamaProvider(model_name=model)
        elif provider == "openai":
            key = self._get_key("openai", selection.profile)
            return OpenAIProvider(model_name=model, api_key=key)
        elif provider == "anthropic":
            key = self._get_key("anthropic", selection.profile)
            return AnthropicProvider(model_name=model, api_key=key)
        elif provider == "google":
            key = self._get_key("google", selection.profile)
            return GoogleProvider(model_name=model, api_key=key)
        else:
            raise ProviderError(f"Unknown provider: '{provider}'")

    def _get_key(self, provider: str, profile: str) -> str:
        """Retrieve an API key from the credential store."""
        if self._credential_store is None:
            raise AuthenticationError("Credential store not initialised", provider=provider)
        return self._credential_store.get_key(provider, profile)

    # ── Audit ────────────────────────────────────────────────────────────

    def _audit(
        self,
        phase: int,
        provider: str,
        model: str,
        usage: TokenUsage,
        success: bool,
        error: str = "",
    ) -> None:
        """Record an inference request in the audit log."""
        from datetime import datetime, timezone
        entry = AuditEntry(
            phase=phase,
            provider=provider,
            model=model,
            timestamp=datetime.now(timezone.utc).isoformat(),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            estimated_cost_usd=usage.estimated_cost_usd,
            privacy_tier=self._config.privacy_tier.value if self._config else "unknown",
            success=success,
            error=error,
        )
        self._audit_log.append(entry)

    def save_audit_log(self, project_dir: Path | None = None) -> None:
        """Persist the audit log to a JSON file in the project workspace."""
        if not self._audit_log:
            return
        import json
        from datetime import datetime, timezone

        target = (project_dir or Path.cwd()) / "logs" / "provider_audit.json"
        target.parent.mkdir(parents=True, exist_ok=True)

        entries = [
            {
                "phase": e.phase,
                "provider": e.provider,
                "model": e.model,
                "timestamp": e.timestamp,
                "prompt_tokens": e.prompt_tokens,
                "completion_tokens": e.completion_tokens,
                "estimated_cost_usd": e.estimated_cost_usd,
                "privacy_tier": e.privacy_tier,
                "success": e.success,
                "error": e.error,
            }
            for e in self._audit_log
        ]

        # Append to existing log
        existing: list[dict[str, Any]] = []
        if target.exists():
            try:
                existing = json.loads(target.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        existing.extend(entries)
        target.write_text(json.dumps(existing, indent=2))

    # ── Config Loading ───────────────────────────────────────────────────

    def _load_or_default(self) -> RoutingConfig:
        """Load config from TOML file or return defaults."""
        cfg = RoutingConfig()

        if not self.config_path.exists():
            return cfg

        try:
            import tomllib
            raw = tomllib.loads(self.config_path.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            return cfg

        # System-level settings
        sys_cfg = raw.get("system", {})
        if "routing_mode" in sys_cfg:
            try:
                cfg.mode = RoutingMode(sys_cfg["routing_mode"])
            except ValueError:
                pass
        if "privacy_tier" in sys_cfg:
            try:
                cfg.privacy_tier = PrivacyTier(sys_cfg["privacy_tier"])
            except ValueError:
                pass
        if "hardware_tier" in sys_cfg and sys_cfg["hardware_tier"] != "auto":
            try:
                cfg.hardware_tier = ModelTier(sys_cfg["hardware_tier"])
            except ValueError:
                pass
        if "latency_budget_seconds" in sys_cfg:
            cfg.latency_budget_seconds = int(sys_cfg["latency_budget_seconds"])

        # Quality mode: cloud-preferred phases
        if "cloud_preferred_phases" in sys_cfg:
            cfg.cloud_preferred_phases = set(int(p) for p in sys_cfg["cloud_preferred_phases"])

        return cfg


# ── Factory ──────────────────────────────────────────────────────────────────


_router_instance: ProviderRouter | None = None


def get_router(
    config_path: Path | None = None,
    project_id: str = "",
    interactive: bool = False,
    force_reinit: bool = False,
) -> ProviderRouter:
    """Get or create the singleton ProviderRouter instance.

    Args:
        config_path: Path to config file. Defaults to ~/.config/hoard/config.yaml.
        project_id: Project ID for audit log scoping.
        interactive: If True, format init output as user-facing wizard text.
        force_reinit: If True, re-initialise even if already initialised.

    Returns:
        Initialised ProviderRouter.
    """
    global _router_instance
    if _router_instance is None or force_reinit:
        _router_instance = ProviderRouter(config_path=config_path, project_id=project_id)
        _router_instance.initialise(interactive=interactive)
    return _router_instance
