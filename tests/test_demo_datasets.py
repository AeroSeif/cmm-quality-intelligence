from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.excel_reader import extract_batch, validate_cross_report
from core.repeatability import analyse_dimensional_repeatability


def load_study(folder_name):
    files = sorted((ROOT / "Data" / folder_name).glob("*.xlsx"))
    assert files, f"No demo workbooks found in Data/{folder_name}"
    records, row_issues, file_summary = extract_batch(files)
    cross_issues = validate_cross_report(records)
    return files, records, row_issues, file_summary, cross_issues


def test_repeatability_demo_is_one_component_and_extracts():
    files, records, row_issues, file_summary, cross = load_study("Repeatability")
    assert len(files) == 10
    assert len(file_summary) == 10
    assert (file_summary["status"] == "read").all()
    assert records["serial_number"].nunique() == 1
    assert len(records) == 370
    assert cross.empty


def test_part_variation_demo_has_distinct_components():
    files, records, row_issues, file_summary, cross = load_study("Part_Variation")
    assert len(files) == 25
    assert (file_summary["status"] == "read").all()
    assert records["serial_number"].nunique() == 25
    assert len(records) == 925
    assert cross.empty
    dimensions = records[records["characteristic_type"] == "dimension"].copy()
    out_of_spec = (dimensions["actual"] < dimensions["lower_spec_limit"]) | (dimensions["actual"] > dimensions["upper_spec_limit"])
    assert int(out_of_spec.sum()) > 0  # Mixed demo includes a small, intentional synthetic Pareto example.


def test_repeatability_engine_runs_on_repeatability_demo():
    _, records, _, _, _ = load_study("Repeatability")
    results, errors = analyse_dimensional_repeatability(records)
    assert len(results) == 20
    assert errors.empty
    assert set(results["acceptance_status"]).issubset({"PASS", "FAIL"})


def test_repeatability_and_part_variation_are_not_same_population():
    _, repeat_records, _, _, _ = load_study("Repeatability")
    _, part_records, _, _, _ = load_study("Part_Variation")
    repeat_actual = repeat_records.loc[repeat_records.characteristic_type == "dimension", "actual"].reset_index(drop=True)
    part_actual = part_records.loc[part_records.characteristic_type == "dimension", "actual"].reset_index(drop=True)
    assert len(repeat_actual) != len(part_actual)
    assert repeat_records["serial_number"].nunique() != part_records["serial_number"].nunique()
