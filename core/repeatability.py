"""Dimensional repeatability calculations for CMM measurement studies.

This module deliberately separates:
- statistical repeatability estimate (6 * sample standard deviation / tolerance),
- observed range (max - min),
- acceptance evaluation against a selected rules profile.

Geometric tolerance data is not evaluated by this dimensional method.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional
import math
import pandas as pd
import numpy as np


@dataclass
class RepeatabilityResult:
    characteristic_key: str
    identifier: str
    classification: Optional[str]
    number_of_runs: int
    nominal: float
    lower_spec_limit: float
    upper_spec_limit: float
    total_tolerance: float
    mean: float
    sample_standard_deviation: float
    study_variation_6s: float
    observed_minimum: float
    observed_maximum: float
    observed_range: float
    repeatability_pct: float
    observed_range_pct: float
    acceptance_limit_pct: Optional[float]
    acceptance_status: str
    warning_status: str
    rules_profile: str
    classification_source: str


def default_as13003_limits() -> dict[str, float]:
    """Reference limits used for this project; purchaser requirements take precedence."""
    return {"critical": 10.0, "major": 20.0, "minor": 30.0}


def calculate_characteristic(
    group: pd.DataFrame,
    rules_profile: str = "AS13003A_reference",
    custom_limits: Optional[dict[str, float]] = None,
    near_limit_fraction: float = 0.80,
) -> RepeatabilityResult:
    if group.empty:
        raise ValueError("No measurements supplied for characteristic.")

    first = group.iloc[0]
    key = str(first["characteristic_key"])
    identifier = str(first["identifier"])

    if not (group["characteristic_type"] == "dimension").all():
        raise ValueError(f"{key}: dimensional repeatability method cannot process geometric data.")

    for field in ("nominal", "lower_spec_limit", "upper_spec_limit"):
        vals = pd.to_numeric(group[field], errors="coerce").dropna().unique()
        if len(vals) != 1:
            raise ValueError(f"{key}: expected one consistent {field}; found {len(vals)} values.")

    lower = float(first["lower_spec_limit"])
    upper = float(first["upper_spec_limit"])
    nominal = float(first["nominal"])
    tolerance = upper - lower
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError(f"{key}: total tolerance must be positive.")

    readings = pd.to_numeric(group["actual"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(readings) < 2:
        raise ValueError(f"{key}: at least two valid readings are required for sample standard deviation.")
    if not np.isfinite(readings).all():
        raise ValueError(f"{key}: readings contain non-finite values.")

    classification = first.get("classification")
    classification_text = str(classification).strip().lower() if pd.notna(classification) else ""
    limits = custom_limits or default_as13003_limits()
    limit = limits.get(classification_text)

    if limit is None:
        raise ValueError(
            f"{key}: no acceptance limit available for classification "
            f"{classification!r}. Supply an approved classification/rules profile."
        )

    mean = float(np.mean(readings))
    sd = float(np.std(readings, ddof=1))
    study_variation = 6.0 * sd
    observed_range = float(np.max(readings) - np.min(readings))
    repeatability_pct = study_variation / tolerance * 100.0
    observed_range_pct = observed_range / tolerance * 100.0

    acceptance = "PASS" if repeatability_pct <= limit else "FAIL"
    warning = "NEAR_LIMIT" if acceptance == "PASS" and repeatability_pct >= near_limit_fraction * limit else "NORMAL"
    class_source = first.get("classification_source")
    class_source = str(class_source) if pd.notna(class_source) else "not_recorded"

    return RepeatabilityResult(
        characteristic_key=key,
        identifier=identifier,
        classification=str(classification) if pd.notna(classification) else None,
        number_of_runs=int(len(readings)),
        nominal=nominal,
        lower_spec_limit=lower,
        upper_spec_limit=upper,
        total_tolerance=tolerance,
        mean=mean,
        sample_standard_deviation=sd,
        study_variation_6s=study_variation,
        observed_minimum=float(np.min(readings)),
        observed_maximum=float(np.max(readings)),
        observed_range=observed_range,
        repeatability_pct=repeatability_pct,
        observed_range_pct=observed_range_pct,
        acceptance_limit_pct=float(limit),
        acceptance_status=acceptance,
        warning_status=warning,
        rules_profile=rules_profile,
        classification_source=class_source,
    )


def analyse_dimensional_repeatability(
    records: pd.DataFrame,
    rules_profile: str = "AS13003A_reference",
    custom_limits: Optional[dict[str, float]] = None,
    near_limit_fraction: float = 0.80,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return characteristic-level results and analysis errors.

    Only dimensional records are analysed. Geometric records are excluded and
    should be handled by a separately validated geometric methodology.
    """
    if records.empty:
        return pd.DataFrame(), pd.DataFrame()

    dimensions = records[records["characteristic_type"] == "dimension"].copy()
    results, errors = [], []

    for key, group in dimensions.groupby("characteristic_key", sort=False):
        try:
            result = calculate_characteristic(
                group,
                rules_profile=rules_profile,
                custom_limits=custom_limits,
                near_limit_fraction=near_limit_fraction,
            )
            results.append(asdict(result))
        except Exception as exc:
            errors.append({
                "characteristic_key": key,
                "identifier": str(group["identifier"].iloc[0]),
                "error": str(exc),
            })

    return pd.DataFrame(results), pd.DataFrame(errors)


def compare_with_expected(
    calculated: pd.DataFrame,
    expected_csv: str,
    tolerance_abs: float = 0.02,
) -> pd.DataFrame:
    """Compare dimensional calculations with generator's expected-results file."""
    expected = pd.read_csv(expected_csv)
    expected = expected[expected["type"].astype(str).str.lower() == "dimension"]
    merged = calculated.merge(
        expected[["characteristic_key", "expected_repeatability_pct", "expected_test_status"]],
        on="characteristic_key",
        how="left",
        validate="one_to_one",
    )
    merged["absolute_difference_pct_points"] = (
        merged["repeatability_pct"] - merged["expected_repeatability_pct"]
    ).abs()
    merged["percentage_matches_expected"] = merged["absolute_difference_pct_points"] <= tolerance_abs
    merged["status_matches_expected"] = merged["acceptance_status"] == merged["expected_test_status"]
    return merged
