"""Immutable Byelingua product-contract V1.

This module is the single repository-level declaration of the product
semantics that ingestion must preserve.  It deliberately contains guards and
metadata only; it does not infer semantics or change the Event Detail UI.
"""

from __future__ import annotations

from typing import Any, MutableMapping


BYELINGUA_PRODUCT_CONTRACT_VERSION = 1
PRODUCT_CONTRACT_VERSION = BYELINGUA_PRODUCT_CONTRACT_VERSION
PRODUCT_CONTRACT_ID = f"BYELINGUA_PRODUCT_CONTRACT_VERSION={BYELINGUA_PRODUCT_CONTRACT_VERSION}"
PRODUCT_CONTRACT_STATUS = "PERMANENT_FROZEN_NON_NEGOTIABLE"

INGESTION_STAGES = (
    "SOURCE",
    "SEGMENT",
    "STRUCTURE",
    "NORMALIZE",
    "CANONICAL_RESOLVE",
    "SEMANTIC_DEDUP",
    "PRODUCT_CONTRACT_VALIDATION",
    "PRODUCTION_WRITE",
)


class ProductContractViolation(RuntimeError):
    """Raised when a workflow does not explicitly remain compatible with V1."""


def assert_product_contract_compatibility(
    declared_version: Any = BYELINGUA_PRODUCT_CONTRACT_VERSION,
    *,
    explicit_product_contract_change: bool = False,
) -> int:
    """Require every ingestion/write path to declare compatibility with V1.

    A product-contract change is intentionally rejected here.  It must be a
    separate, explicit product task; parser, enrichment, cleanup, and deploy
    workflows cannot silently introduce a new semantic version.
    """
    if explicit_product_contract_change:
        raise ProductContractViolation(
            "EXPLICIT_PRODUCT_CONTRACT_CHANGE=YES requires a dedicated product-contract task"
        )
    try:
        version = int(declared_version)
    except (TypeError, ValueError) as exc:
        raise ProductContractViolation("product contract compatibility must declare V1") from exc
    if version != BYELINGUA_PRODUCT_CONTRACT_VERSION:
        raise ProductContractViolation(
            f"incompatible product contract version: {version}; expected {BYELINGUA_PRODUCT_CONTRACT_VERSION}"
        )
    return version


def declare_product_contract(
    payload: MutableMapping[str, Any],
    *,
    declared_version: Any = BYELINGUA_PRODUCT_CONTRACT_VERSION,
) -> MutableMapping[str, Any]:
    """Attach the immutable contract declaration to an artifact or payload."""
    version = assert_product_contract_compatibility(declared_version)
    payload["product_contract_version"] = version
    payload["product_contract_id"] = PRODUCT_CONTRACT_ID
    payload["product_contract_status"] = PRODUCT_CONTRACT_STATUS
    return payload


def validate_product_contract_metadata(payload: Any) -> int:
    """Validate a serialized artifact's V1 declaration before a production write."""
    if not isinstance(payload, dict):
        raise ProductContractViolation("product contract metadata requires an object payload")
    version = assert_product_contract_compatibility(payload.get("product_contract_version"))
    if payload.get("product_contract_id") != PRODUCT_CONTRACT_ID:
        raise ProductContractViolation("product contract id is missing or does not identify V1")
    return version

