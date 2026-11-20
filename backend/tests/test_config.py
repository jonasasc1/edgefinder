from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from edgefinder.config import FACTORS, AssetClass, Config, Secrets, load_config, load_secrets

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_shipped_config_is_valid() -> None:
    config = load_config(REPO_ROOT / "config.yaml")

    assert config.server.port == 8420
    assert set(config.profiles) == {"swing", "long_term"}
    assert len(config.assets.forex) == 14
    assert {asset.id for asset in config.assets.indices} == {"SPX", "NDX", "DJI", "DAX", "NIKKEI"}
    assert {asset.id for asset in config.assets.commodities} == {"GOLD", "SILVER", "WTI", "COPPER"}
    assert len(config.assets.stocks) == 20


def test_every_asset_has_price_symbol_and_unique_id(config: Config) -> None:
    assets = config.assets.all()
    assert len(config.assets_by_id) == len(assets)
    assert config.assets_by_id["BRKB"].price_symbol == "BRK-B"
    assert config.assets_by_id["EURUSD"].yfinance == "EURUSD=X"


def test_profiles_cover_all_factors(config: Config) -> None:
    for profile in config.profiles.values():
        for asset_class in AssetClass:
            assert set(profile.weights[asset_class]) == FACTORS[asset_class]
            assert sum(profile.weights[asset_class].values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (10, "Stark bullish"),
        (6, "Stark bullish"),
        (5.9, "Bullish"),
        (2, "Bullish"),
        (0, "Neutral"),
        (-2, "Neutral"),
        (-2.1, "Bearish"),
        (-6, "Bearish"),
        (-6.1, "Stark bearish"),
        (-10, "Stark bearish"),
    ],
)
def test_score_labels(config: Config, score: float, label: str) -> None:
    assert config.scoring.label_for(score) == label


def test_weights_must_sum_to_one(config_data: dict[str, Any]) -> None:
    config_data["profiles"]["swing"]["weights"]["forex"]["trend"] = 0.5
    with pytest.raises(ValidationError, match="summieren sich"):
        Config.model_validate(config_data)


def test_unknown_factor_is_rejected(config_data: dict[str, Any]) -> None:
    weights = config_data["profiles"]["swing"]["weights"]["forex"]
    weights["astrology"] = weights.pop("trend")
    with pytest.raises(ValidationError, match="unbekannt"):
        Config.model_validate(config_data)


def test_duplicate_asset_id_is_rejected(config_data: dict[str, Any]) -> None:
    config_data["assets"]["stocks"].append({"id": "GOLD", "name": "Doppelt", "ticker": "GLD"})
    with pytest.raises(ValidationError, match="doppelt"):
        Config.model_validate(config_data)


def test_unknown_currency_is_rejected(config_data: dict[str, Any]) -> None:
    config_data["assets"]["forex"][0]["base"] = "XXX"
    with pytest.raises(ValidationError, match="unbekannte Währung"):
        Config.model_validate(config_data)


def test_unknown_keys_are_rejected(config_data: dict[str, Any]) -> None:
    config_data["server"]["prot"] = 1
    with pytest.raises(ValidationError):
        Config.model_validate(config_data)


def test_retry_falls_back_to_global_default(config_data: dict[str, Any]) -> None:
    config_data["sources"]["aaii"]["retry"] = {
        "attempts": 2,
        "backoff_seconds": 30,
        "max_backoff_seconds": 120,
        "timeout_seconds": 20,
    }
    config = Config.model_validate(config_data)

    assert config.retry_for("aaii").attempts == 2
    assert config.retry_for("cftc") == config.retry


def test_secrets_treat_empty_values_as_missing(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FRED_API_KEY=\nCONTACT_EMAIL=test@example.org\n", encoding="utf-8")

    secrets = load_secrets(env_file)

    assert secrets.fred_api_key is None
    assert secrets.contact_email is not None
    assert secrets.contact_email.get_secret_value() == "test@example.org"
    assert "test@example.org" not in repr(secrets)


def test_env_example_lists_every_secret() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for field in Secrets.model_fields:
        assert f"{field.upper()}=" in example


def test_us_extra_macro_indicators_and_pmi_substitute_is_labelled() -> None:
    """Neue US-Reihen (live geprüft 2026-11-20); Regional-Fed-Indizes heißen PMI-Ersatz."""
    from edgefinder.config import load_config

    us = load_config().economies["US"].indicators
    for key in ("consumer_confidence", "ppi", "pce", "core_pce", "durable_goods", "housing_starts"):
        assert key in us
    assert {"jolts", "adp"} <= set(us) and us["adp"].series == "ADPMNUSNERSA"
    assert (
        us["philly_fed"].series == "GACDFSA066MSFRBPHI" and "PMI-Ersatz" in us["philly_fed"].label
    )
    assert "ISM" not in " ".join(i.label for i in us.values())
