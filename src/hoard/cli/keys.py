"""keys.py — `hoard keys` CLI subcommand for credential management.

Registered by main.py as a Typer sub-app. Uses the CredentialStore to
manage encrypted API keys for cloud providers.

Usage:
    hoard keys unlock
    hoard keys set openai sk-...
    hoard keys list
    hoard keys remove openai
"""

from __future__ import annotations


import typer
from rich.console import Console
from rich.table import Table

from hoard.providers.credentials import CredentialStore

console = Console()
keys_app = typer.Typer(
    name="keys",
    help="Manage encrypted API keys for cloud providers",
    no_args_is_help=True,
)


@keys_app.command("unlock")
def keys_unlock(
    password: str = typer.Option(
        "", "--password", "-p",
        help="Master password (or set HOARD_VAULT_KEY env var)",
    ),
) -> None:
    """Unlock the credential vault and load keys into memory."""
    store = CredentialStore()
    if store.unlock(password):
        providers = store.list_providers()
        console.print(f"[green]✓[/] Vault unlocked with {len(providers)} key(s)")
        for p in providers:
            console.print(f"  • {p['provider']} ({p['profile']}): {p['key_prefix']}")
    else:
        console.print("[red]✗[/] Failed to unlock vault.")
        console.print("  Check your master password, or initialise with [bold]hoard keys set <provider> <key>[/]")
        raise typer.Exit(1)


@keys_app.command("set")
def keys_set(
    provider: str = typer.Argument(..., help="Provider name (openai, anthropic, google)"),
    key: str = typer.Argument(..., help="API key"),
    profile: str = typer.Option("default", "--profile", help="Key profile name"),
    password: str = typer.Option(
        "", "--password", "-p",
        help="Master password (if vault already exists)",
    ),
) -> None:
    """Store an encrypted API key for a cloud provider."""
    store = CredentialStore()

    if store.is_initialised():
        if not store.unlock(password):
            console.print("[red]✗[/] Failed to unlock existing vault.")
            console.print("  Use --password or set HOARD_VAULT_KEY environment variable.")
            raise typer.Exit(1)
    else:
        # First key — initialise vault
        if not password:
            # Use env var or prompt
            import os
            password = os.environ.get("HOARD_VAULT_KEY", "")
            if not password:
                password = typer.prompt("Create master password for credential vault", hide_input=True)
        store.initialise(password)

    store.set_key(provider, key, profile)
    console.print(f"[green]✓[/] Key stored for [bold]{provider}[/] (profile: {profile})")
    console.print(f"  Vault: {store.vault_path}")


@keys_app.command("list")
def keys_list(
    password: str = typer.Option(
        "", "--password", "-p",
        help="Master password",
    ),
) -> None:
    """List configured providers and masked key prefixes."""
    store = CredentialStore()
    if not store.unlock(password):
        console.print("[red]✗[/] Failed to unlock vault.")
        console.print("  Use [bold]hoard keys unlock[/] first.")
        raise typer.Exit(1)

    providers = store.list_providers()
    if not providers:
        console.print("[yellow]ℹ[/] No API keys configured.")
        return

    table = Table(title="Configured API Keys")
    table.add_column("Provider", style="cyan")
    table.add_column("Profile", style="green")
    table.add_column("Key", style="yellow")
    for p in providers:
        table.add_row(p["provider"], p["profile"], p["key_prefix"])
    console.print(table)


@keys_app.command("remove")
def keys_remove(
    provider: str = typer.Argument(..., help="Provider name"),
    profile: str = typer.Option("default", "--profile", help="Key profile name"),
    password: str = typer.Option(
        "", "--password", "-p",
        help="Master password",
    ),
) -> None:
    """Remove a stored API key from the vault."""
    store = CredentialStore()
    if not store.unlock(password):
        console.print("[red]✗[/] Failed to unlock vault.")
        raise typer.Exit(1)

    if store.remove_key(provider, profile):
        console.print(f"[green]✓[/] Key removed for [bold]{provider}[/] (profile: {profile})")
    else:
        console.print(f"[red]✗[/] No key found for [bold]{provider}[/] (profile: {profile})")


@keys_app.command("init")
def keys_init(
    password: str = typer.Option(
        "", "--password", "-p",
        help="Master password (or set HOARD_VAULT_KEY env var)",
    ),
) -> None:
    """Initialise a new empty credential vault."""
    store = CredentialStore()
    if store.is_initialised():
        console.print("[yellow]⚠[/] Vault already exists at:")
        console.print(f"  {store.vault_path}")
        console.print("  Use [bold]hoard keys set[/] to add keys.")
        return

    if not password:
        import os
        password = os.environ.get("HOARD_VAULT_KEY", "")
        if not password:
            password = typer.prompt("Create master password for credential vault", hide_input=True)

    store.initialise(password)
    console.print(f"[green]✓[/] Vault initialised at: {store.vault_path}")
    console.print("  Use [bold]hoard keys set <provider> <key>[/] to add API keys.")
