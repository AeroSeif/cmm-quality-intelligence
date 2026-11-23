from pathlib import Path
import argparse
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from core.excel_reader import extract_batch, validate_cross_report
from core.repeatability import analyse_dimensional_repeatability

def main():
    parser=argparse.ArgumentParser(description="Analyse one CMM study dataset.")
    parser.add_argument("--study",choices=["repeatability","part_variation"],default="repeatability")
    parser.add_argument("--data-dir",default=None,help="Optional explicit folder containing inspection workbooks.")
    args=parser.parse_args()
    folder=Path(args.data_dir) if args.data_dir else ROOT/"Data"/("Repeatability" if args.study=="repeatability" else "Part_Variation")
    if not folder.is_absolute():
        folder = ROOT / folder
    output=ROOT/"outputs"/args.study
    output.mkdir(parents=True,exist_ok=True)
    files=sorted(list(folder.glob("*.xlsx"))+list(folder.glob("*.xlsm")))
    if not files:
        print(f"ERROR: No Excel workbooks found in {folder}")
        print("Generate a dataset first, or supply --data-dir.")
        return 1
    records,issues,file_summary=extract_batch(files)
    cross=validate_cross_report(records)
    records.to_csv(output/"consolidated_measurements.csv",index=False)
    pd.concat([issues,cross],ignore_index=True,sort=False).to_csv(output/"validation_issues.csv",index=False)
    file_summary.to_csv(output/"file_summary.csv",index=False)
    if records.empty:
        print("ERROR: No records extracted."); return 1
    if args.study=="repeatability":
        results,errors=analyse_dimensional_repeatability(records)
        results.to_csv(output/"repeatability_results.csv",index=False)
        errors.to_csv(output/"calculation_errors.csv",index=False)
        print(f"Repeatability characteristics: {len(results)}")
        if not results.empty:
            print("PASS:",int((results.acceptance_status=="PASS").sum()))
            print("FAIL:",int((results.acceptance_status=="FAIL").sum()))
    else:
        dims=records[records.characteristic_type=="dimension"].copy()
        summary=dims.groupby("characteristic_key").agg(
            identifier=("identifier","first"),n_readings=("actual","count"),
            mean_actual=("actual","mean"),standard_deviation=("actual","std"),
            minimum=("actual","min"),maximum=("actual","max")).reset_index()
        summary["observed_spread"]=summary.maximum-summary.minimum
        summary.to_csv(output/"part_variation_summary.csv",index=False)
        print(f"Part-variation characteristics: {len(summary)}")
    print(f"Workbooks read: {(file_summary.status=='read').sum()}/{len(file_summary)}")
    print(f"Records extracted: {len(records)}")
    print(f"Outputs: {output.resolve()}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
