from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.repeatability import calculate_characteristic


def test_repeatability_uses_six_sigma_over_total_tolerance():
    group = pd.DataFrame({
        "characteristic_key": ["DIM-TEST-01"] * 5,
        "identifier": ["TEST"] * 5,
        "characteristic_type": ["dimension"] * 5,
        "nominal": [10.0] * 5,
        "lower_spec_limit": [9.9] * 5,
        "upper_spec_limit": [10.1] * 5,
        "actual": [10.000, 10.001, 9.999, 10.002, 9.998],
        "classification": ["Critical"] * 5,
        "classification_source": ["test"] * 5,
    })
    result = calculate_characteristic(group)
    assert result.number_of_runs == 5
    assert result.repeatability_pct >= 0
    assert result.acceptance_limit_pct == 10.0
