import pytest

from season_ingestion.product_contract import (
    BYELINGUA_PRODUCT_CONTRACT_VERSION,
    PRODUCT_CONTRACT_ID,
    ProductContractViolation,
    assert_product_contract_compatibility,
    declare_product_contract,
    validate_product_contract_metadata,
)


def test_repository_product_contract_is_v1():
    assert BYELINGUA_PRODUCT_CONTRACT_VERSION == 1
    assert PRODUCT_CONTRACT_ID == "BYELINGUA_PRODUCT_CONTRACT_VERSION=1"


def test_ingestion_must_declare_v1_compatibility():
    assert assert_product_contract_compatibility(1) == 1
    with pytest.raises(ProductContractViolation):
        assert_product_contract_compatibility(2)
    with pytest.raises(ProductContractViolation):
        assert_product_contract_compatibility(1, explicit_product_contract_change=True)


def test_artifact_contract_metadata_is_attached_and_verified():
    payload = declare_product_contract({"stage": "final_staging"})
    assert payload["product_contract_version"] == 1
    assert validate_product_contract_metadata(payload) == 1
    with pytest.raises(ProductContractViolation):
        validate_product_contract_metadata({"product_contract_version": 1})

