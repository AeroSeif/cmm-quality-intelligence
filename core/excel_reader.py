"""Excel extraction engine for the synthetic CMM inspection workbook template.

This module extracts source records without making engineering acceptance decisions.
Repeated identifiers are preserved as separate characteristics using occurrence and row
position. Synthetic test classifications are read from the optional Test Configuration
worksheet and are explicitly marked as test metadata.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
import math
import re

import pandas as pd
from openpyxl import load_workbook

HEADER_LABELS = {
    "drawing_number": "Drawing No",
    "order_number": "Order No",
    "inspection_date": "Date",
    "title": "Title",
    "serial_number": "Serial No",
    "inspector": "Inspector",
    "customer": "Customer",
    "material_reference": "Material Ref",
    "notes": "Notes",
}

EXPECTED_COLUMNS = [
    "Identifier",
    "Dimension — Nominal",
    "Dimension — Actual",
    "Dimension — Error",
    "Limit/Tolerance — Upper",
    "Limit/Tolerance — Lower",
    "Dimension Pass/Fail",
    "Geometric Tolerance — Actual",
    "Geometric Tolerance — Limit",
    "Geometric Tolerance — Pass/Fail",
]

def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value

def _number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        try:
            result = float(s)
            return result if math.isfinite(result) else None
        except ValueError:
            return None
    return None

def _find_label_value(ws, label):
    """Find a label anywhere in the first 12 rows and return the cell to its right."""
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 12)):
        for cell in row:
            if isinstance(cell.value, str) and cell.value.strip().rstrip(":") == label:
                # The value may be in the immediately adjacent cell.
                return _clean(ws.cell(cell.row, cell.column + 1).value)
    return None

def _find_header_row(ws):
    for row_idx in range(1, ws.max_row + 1):
        vals = [_clean(ws.cell(row_idx, c).value) for c in range(1, ws.max_column + 1)]
        if vals and vals[0] == "Identifier" and "Dimension — Actual" in vals:
            return row_idx
    raise ValueError(f"Could not locate inspection table headers in worksheet '{ws.title}'")

def _classification_map(wb):
    """Read optional synthetic classification metadata; never infer classifications."""
    if "Test Configuration" not in wb.sheetnames:
        return {}
    ws = wb["Test Configuration"]
    headers = [_clean(ws.cell(8, c).value) for c in range(1, ws.max_column + 1)]
    positions = {str(v): i + 1 for i, v in enumerate(headers) if v is not None}
    required = {"Characteristic Key", "Classification", "Synthetic Scenario",
                "Configured Test Limit (%)", "Target Repeatability (%)"}
    if not required.issubset(positions):
        return {}
    result = {}
    for r in range(9, ws.max_row + 1):
        key = _clean(ws.cell(r, positions["Characteristic Key"]).value)
        if not key:
            continue
        result[str(key)] = {
            "classification": _clean(ws.cell(r, positions["Classification"]).value),
            "synthetic_scenario": _clean(ws.cell(r, positions["Synthetic Scenario"]).value),
            "configured_test_limit_pct": _number(ws.cell(r, positions["Configured Test Limit (%)"]).value),
            "target_repeatability_pct": _number(ws.cell(r, positions["Target Repeatability (%)"]).value),
            "classification_source": "synthetic_test_configuration",
        }
    return result

def extract_workbook(path: str | Path, sheet_name: str = "Inspection Report") -> tuple[dict, list[dict], list[dict]]:
    path = Path(path)
    wb = load_workbook(path, data_only=True, read_only=False)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"Worksheet '{sheet_name}' not found in {path.name}; found {wb.sheetnames}")
    ws = wb[sheet_name]

    metadata = {"source_file": path.name}
    for key, label in HEADER_LABELS.items():
        metadata[key] = _find_label_value(ws, label)

    header_row = _find_header_row(ws)
    header_values = [_clean(ws.cell(header_row, c).value) for c in range(1, ws.max_column + 1)]
    col = {str(v): i + 1 for i, v in enumerate(header_values) if v is not None}

    missing_headers = [h for h in EXPECTED_COLUMNS if h not in col]
    if missing_headers:
        raise ValueError(f"Missing expected columns in {path.name}: {missing_headers}")

    test_meta = _classification_map(wb)
    records, issues = [], []
    occurrences = {}
    for r in range(header_row + 1, ws.max_row + 1):
        raw_id = _clean(ws.cell(r, col["Identifier"]).value)
        if raw_id is None:
            continue
        identifier = str(raw_id)
        dim_nom = _number(ws.cell(r, col["Dimension — Nominal"]).value)
        dim_actual = _number(ws.cell(r, col["Dimension — Actual"]).value)
        dim_error = _number(ws.cell(r, col["Dimension — Error"]).value)
        upper = _number(ws.cell(r, col["Limit/Tolerance — Upper"]).value)
        lower = _number(ws.cell(r, col["Limit/Tolerance — Lower"]).value)
        dim_status = _clean(ws.cell(r, col["Dimension Pass/Fail"]).value)
        geo_actual = _number(ws.cell(r, col["Geometric Tolerance — Actual"]).value)
        geo_limit = _number(ws.cell(r, col["Geometric Tolerance — Limit"]).value)
        geo_status = _clean(ws.cell(r, col["Geometric Tolerance — Pass/Fail"]).value)

        has_dim = any(v is not None for v in (dim_nom, dim_actual, dim_error, upper, lower, dim_status))
        has_geo = any(v is not None for v in (geo_actual, geo_limit, geo_status))
        if not has_dim and not has_geo:
            issues.append({
                "source_file": path.name, "worksheet": sheet_name, "row": r,
                "identifier": identifier, "issue": "identifier_row_has_no_measurement_values",
                "severity": "warning"
            })
            continue

        # Separate occurrence counters by measurement family so repeated IDs survive.
        family = "dimension" if has_dim else "geometric"
        occurrence_key = (family, identifier)
        occurrences[occurrence_key] = occurrences.get(occurrence_key, 0) + 1
        occurrence = occurrences[occurrence_key]
        characteristic_key = f"{'DIM' if family == 'dimension' else 'GEO'}-{identifier}-{occurrence:02d}"

        if has_dim:
            if dim_actual is None:
                issues.append({"source_file": path.name, "worksheet": sheet_name, "row": r,
                               "identifier": identifier, "issue": "missing_dimensional_actual",
                               "severity": "error"})
            if upper is None or lower is None:
                issues.append({"source_file": path.name, "worksheet": sheet_name, "row": r,
                               "identifier": identifier, "issue": "missing_dimensional_specification_limit",
                               "severity": "error"})
            elif upper <= lower:
                issues.append({"source_file": path.name, "worksheet": sheet_name, "row": r,
                               "identifier": identifier, "issue": "invalid_dimensional_specification_limits",
                               "severity": "error"})
            if dim_actual is not None and dim_nom is not None and dim_error is not None:
                if not math.isclose(dim_actual - dim_nom, dim_error, rel_tol=1e-7, abs_tol=1e-7):
                    issues.append({"source_file": path.name, "worksheet": sheet_name, "row": r,
                                   "identifier": identifier, "issue": "reported_error_does_not_match_actual_minus_nominal",
                                   "severity": "warning"})
            record = {
                **metadata, "source_worksheet": sheet_name, "source_row": r,
                "characteristic_key": characteristic_key, "identifier": identifier,
                "occurrence": occurrence, "characteristic_type": "dimension",
                "nominal": dim_nom, "actual": dim_actual, "reported_error": dim_error,
                "upper_spec_limit": upper, "lower_spec_limit": lower,
                "total_tolerance": (upper - lower) if upper is not None and lower is not None else None,
                "source_pass_fail": dim_status,
                "geometric_actual": None, "geometric_limit": None, "geometric_pass_fail": None,
                "classification": None, "synthetic_scenario": None,
                "configured_test_limit_pct": None, "target_repeatability_pct": None,
                "classification_source": None,
            }
        else:
            if geo_actual is None:
                issues.append({"source_file": path.name, "worksheet": sheet_name, "row": r,
                               "identifier": identifier, "issue": "missing_geometric_actual",
                               "severity": "error"})
            if geo_limit is None or geo_limit <= 0:
                issues.append({"source_file": path.name, "worksheet": sheet_name, "row": r,
                               "identifier": identifier, "issue": "missing_or_invalid_geometric_limit",
                               "severity": "error"})
            record = {
                **metadata, "source_worksheet": sheet_name, "source_row": r,
                "characteristic_key": characteristic_key, "identifier": identifier,
                "occurrence": occurrence, "characteristic_type": "geometric",
                "nominal": None, "actual": None, "reported_error": None,
                "upper_spec_limit": None, "lower_spec_limit": None,
                "total_tolerance": None, "source_pass_fail": None,
                "geometric_actual": geo_actual, "geometric_limit": geo_limit,
                "geometric_pass_fail": geo_status,
                "classification": None, "synthetic_scenario": None,
                "configured_test_limit_pct": None, "target_repeatability_pct": None,
                "classification_source": None,
            }

        # Match synthetic metadata by family + identifier + occurrence.
        config_key = f"{'DIM' if family == 'dimension' else 'GEO'}-{identifier}-{occurrence:02d}"
        if config_key in test_meta:
            record.update(test_meta[config_key])
        records.append(record)

    wb.close()
    return metadata, records, issues

def extract_batch(paths: Iterable[str | Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_records, all_issues, file_rows = [], [], []
    for item in paths:
        path = Path(item)
        try:
            metadata, records, issues = extract_workbook(path)
            all_records.extend(records)
            all_issues.extend(issues)
            file_rows.append({"source_file": path.name, "status": "read",
                              "records_extracted": len(records), "issues": len(issues),
                              "drawing_number": metadata.get("drawing_number"),
                              "serial_number": metadata.get("serial_number")})
        except Exception as exc:
            file_rows.append({"source_file": path.name, "status": "failed",
                              "records_extracted": 0, "issues": 1,
                              "error": str(exc)})
            all_issues.append({"source_file": path.name, "worksheet": None, "row": None,
                               "identifier": None, "issue": f"workbook_read_failed: {exc}",
                               "severity": "error"})
    return pd.DataFrame(all_records), pd.DataFrame(all_issues), pd.DataFrame(file_rows)

def validate_cross_report(records: pd.DataFrame) -> pd.DataFrame:
    """Check consistency of nominal/specification values for matched dimensions."""
    if records.empty:
        return pd.DataFrame()
    issues = []
    dimensions = records[records["characteristic_type"] == "dimension"]
    for key, group in dimensions.groupby("characteristic_key", dropna=False):
        for field in ("nominal", "upper_spec_limit", "lower_spec_limit"):
            values = group[field].dropna().unique()
            if len(values) > 1:
                issues.append({"characteristic_key": key, "identifier": group["identifier"].iloc[0],
                               "issue": f"inconsistent_{field}_across_reports",
                               "values_found": " | ".join(map(str, sorted(values))),
                               "severity": "error"})
        if group["actual"].isna().any():
            issues.append({"characteristic_key": key, "identifier": group["identifier"].iloc[0],
                           "issue": "missing_actual_in_one_or_more_reports",
                           "values_found": "", "severity": "error"})
    return pd.DataFrame(issues)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract CMM inspection records from Excel workbooks."
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="Excel workbook paths (optional)"
    )

    parser.add_argument(
        "--out",
        default="outputs",
        help="Output directory"
    )

    args = parser.parse_args()

    # Automatically locate the project root
    project_root = Path(__file__).resolve().parents[1]

    # If no files are supplied, search the Data folder
    if args.files:
        input_files = [Path(f) for f in args.files]
    else:
        data_folder = project_root / "Data"

        input_files = sorted(
            data_folder.glob("synthetic_inspection_run_*.xlsx")
        )

    if not input_files:
        print("ERROR: No Excel inspection reports found.")
        print("Check that your Excel files are inside the Data folder.")
        return

    print(f"Found {len(input_files)} inspection reports.")

    output_folder = Path(args.out)

    if not output_folder.is_absolute():
        output_folder = project_root / output_folder

    output_folder.mkdir(parents=True, exist_ok=True)

    # Extract all workbooks
    records, issues, file_summary = extract_batch(input_files)

    # Check consistency between reports
    cross_issues = validate_cross_report(records)

    if not cross_issues.empty:
        cross_issues["source"] = "cross_report"

    combined_issues = pd.concat(
        [issues, cross_issues],
        ignore_index=True,
        sort=False
    )

    # Export CSV files
    records.to_csv(
        output_folder / "consolidated_measurements.csv",
        index=False
    )

    combined_issues.to_csv(
        output_folder / "validation_issues.csv",
        index=False
    )

    file_summary.to_csv(
        output_folder / "file_summary.csv",
        index=False
    )

    # Export Excel workbook
    with pd.ExcelWriter(
        output_folder / "extraction_results.xlsx",
        engine="openpyxl"
    ) as writer:

        records.to_excel(
            writer,
            sheet_name="Measurements",
            index=False
        )

        combined_issues.to_excel(
            writer,
            sheet_name="Validation Issues",
            index=False
        )

        file_summary.to_excel(
            writer,
            sheet_name="File Summary",
            index=False
        )

    # Display results
    print("\n========== EXTRACTION COMPLETE ==========")
    print(f"Files processed: {len(file_summary)}")
    print(f"Successful files: {(file_summary['status'] == 'read').sum()}")
    print(f"Records extracted: {len(records)}")
    print(f"Validation issues: {len(combined_issues)}")
    print(f"Output directory: {output_folder.resolve()}")
    print("=========================================")


if __name__ == "__main__":
    main()
