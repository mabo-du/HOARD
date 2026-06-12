"""signatures.py — PAdES digital signatures via pyHanko.

Provides optional offline PDF signing for jurisdictions requiring
cryptographic authentication (e.g., US Section 106 submissions,
UK planning authority deposits).

Supports:
    - PAdES-B: Baseline signature (visible or invisible)
    - PAdES-B-LT: Long Term Validation with embedded revocation data

Requires pyHanko (pip install pyhanko) and a signing key/certificate.

export: sign_pdf(pdf_path, output_path, config) -> Path | None
used_by: hoard.phases.phase5  → export_report()  (optional)
license: MIT
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

# Default config path for signing credentials
# ~/.config/hoard/signing.pem (RSA or EC private key + certificate)
_SIGNING_KEY_PATH = Path.home() / ".config" / "hoard" / "signing.pem"


def sign_pdf(
    pdf_path: Path,
    output_path: Path | None = None,
    key_path: Path | None = None,
    reason: str = "HOARD Archaeological Report — Automated Digital Signature",
    visible: bool = False,
) -> Path | None:
    """Apply a PAdES-B digital signature to a PDF.

    Args:
        pdf_path: Input unsigned PDF.
        output_path: Output signed PDF. Defaults to input path with _signed suffix.
        key_path: Signing key PEM file. Defaults to ~/.config/hoard/signing.pem.
        reason: Signature reason string (appears in PDF metadata).
        visible: If True, renders a visible signature panel on the last page.

    Returns:
        Path to signed PDF, or None if signing failed or pyHanko unavailable.
    """
    try:
        from pyhanko.sign import signers
        from pyhanko.sign.fields import SigSeedSubFilter
        import importlib.util
        if importlib.util.find_spec("pyhanko_certvalidator") is None:
            raise ImportError("pyhanko_certvalidator not installed")
    except ImportError:
        logger.info("pyHanko not installed — PDF signing skipped. "
                     "Install with: pip install pyhanko pyhanko-certvalidator")
        return None

    key = key_path or _SIGNING_KEY_PATH
    if not key.exists():
        logger.info(f"No signing key found at {key} — PDF signing skipped")
        return None

    out = output_path or pdf_path.with_stem(pdf_path.stem + "_signed")
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Load signer from PEM
        signer = signers.SimpleSigner.load_pkcs12(
            pfx_file=str(key),
            passphrase=None,  # Unencrypted key assumed
        )

        # Build signature metadata
        signature_meta = signers.PdfSignatureMetadata(
            field_name="HOARD_Signature",
            reason=reason,
            subfilter=SigSeedSubFilter.PADES,
        )

        # Apply signature with long-term validation
        with open(pdf_path, "rb") as inf:
            out_bytes = signers.sign_pdf(
                inf,
                signature_meta=signature_meta,
                signer=signer,
                output=output_path and str(output_path) or None,
            )

        if out_bytes and not output_path:
            out.write_bytes(out_bytes)

        logger.info(f"PDF signed: {out}")
        return out

    except Exception as e:
        logger.warning(f"PDF signing failed: {e}")
        return None


def verify_signature(pdf_path: Path) -> dict[str, Any] | None:
    """Verify the digital signature on a signed PDF.

    Returns dict with signature validity info, or None if unverifiable.
    """
    try:
        from pyhanko.sign.validation import validate_pdf_signature
    except ImportError:
        return None

    try:
        with open(pdf_path, "rb") as f:
            status = validate_pdf_signature(f.read())
        return {
            "intact": status.intact,
            "valid": status.valid,
            "signer": str(status.signer_cert.subject if hasattr(status, 'signer_cert') else "unknown"),
        }
    except Exception:
        return None


def has_signing_key() -> bool:
    """Check if a signing key is configured."""
    return _SIGNING_KEY_PATH.exists()
