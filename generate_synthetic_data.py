from __future__ import annotations
from pathlib import Path
import argparse
import math
import random
import re
import shutil
from datetime import datetime
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"Data"
DIM_HEADERS={
    "id":"Identifier","nominal":"Dimension — Nominal","actual":"Dimension — Actual",
    "error":"Dimension — Error","upper":"Limit/Tolerance — Upper","lower":"Limit/Tolerance — Lower",
    "status":"Dimension Pass/Fail",
    "geo_actual":"Geometric Tolerance — Actual","geo_limit":"Geometric Tolerance — Limit",
    "geo_status":"Geometric Tolerance — Pass/Fail",
}

def find_template(explicit=None):
    if explicit:
        p=Path(explicit)
        if not p.is_absolute(): p=ROOT/p
        if not p.exists(): raise FileNotFoundError(p)
        return p
    preferred=DATA/"template.xlsx"
    if preferred.exists(): return preferred
    candidates=[]
    for pattern in ("*.xlsx","*.xlsm"):
        candidates += [p for p in DATA.glob(pattern) if p.name.lower()!="template.xlsx"]
    if not candidates:
        for folder in (DATA/"Repeatability",DATA/"Part_Variation"):
            if folder.exists():
                candidates += list(folder.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError("No template workbook found. Put a known-good inspection workbook at Data/template.xlsx.")
    return sorted(candidates)[0]

def locate_table(ws):
    for r in range(1,ws.max_row+1):
        vals=[ws.cell(r,c).value for c in range(1,ws.max_column+1)]
        if vals and vals[0]=="Identifier" and "Dimension — Actual" in vals:
            cols={str(v):i+1 for i,v in enumerate(vals) if v is not None}
            return r,cols
    raise ValueError("Could not find the inspection table header row.")

def number(v):
    try:
        if v is None: return None
        return float(v)
    except (TypeError,ValueError): return None

def update_serial(ws, serial):
    for row in ws.iter_rows(min_row=1,max_row=min(ws.max_row,12)):
        for cell in row:
            if isinstance(cell.value,str) and cell.value.strip().rstrip(":")=="Serial No":
                ws.cell(cell.row,cell.column+1).value=serial

def update_study_metadata(wb, study, run_number, seed, serial):
    mode = ("Same physical component — repeated synthetic inspections" if study == "repeatability"
            else "Different manufactured components — synthetic part-to-part variation")
    if "Transcription Notes" in wb.sheetnames:
        notes = wb["Transcription Notes"]
        notes["B5"] = ("Ten repeated inspections of one simulated physical component."
                        if study == "repeatability" else
                        "Each workbook represents a different simulated manufactured component.")
        notes["B6"] = serial
        notes["B7"] = seed if seed is not None else "random"
    if "Test Configuration" in wb.sheetnames:
        config = wb["Test Configuration"]
        config["B2"] = mode
        config["B3"] = run_number
        config["B4"] = seed if seed is not None else "random"

def generate(study, count, seed, template, scenario):
    rng=random.Random(seed)
    out_dir=DATA/("Repeatability" if study=="repeatability" else "Part_Variation")
    out_dir.mkdir(parents=True,exist_ok=True)
    # Remove only files created by this generator; leave all other files untouched.
    for old in out_dir.glob("synthetic_*.xlsx"): old.unlink()
    wb0=load_workbook(template,data_only=False)
    if "Inspection Report" not in wb0.sheetnames:
        raise ValueError("Template must contain an 'Inspection Report' worksheet.")
    ws0=wb0["Inspection Report"]
    header,cols=locate_table(ws0)
    features=[]
    occurrences={}
    for r in range(header+1,ws0.max_row+1):
        ident=ws0.cell(r,cols["Identifier"]).value
        if ident is None: continue
        nom=number(ws0.cell(r,cols["Dimension — Nominal"]).value)
        act=number(ws0.cell(r,cols["Dimension — Actual"]).value)
        upper=number(ws0.cell(r,cols["Limit/Tolerance — Upper"]).value)
        lower=number(ws0.cell(r,cols["Limit/Tolerance — Lower"]).value)
        geo=number(ws0.cell(r,cols["Geometric Tolerance — Actual"]).value)
        glimit=number(ws0.cell(r,cols["Geometric Tolerance — Limit"]).value)
        family="dimension" if any(x is not None for x in (nom,act,upper,lower)) else "geometric"
        key=(family,str(ident)); occurrences[key]=occurrences.get(key,0)+1
        if family=="dimension" and None not in (nom,act,upper,lower) and upper>lower:
            features.append({"row":r,"id":str(ident),"nominal":nom,"base":act,"upper":upper,"lower":lower,
                             "occ":occurrences[key],"tol":upper-lower})
        elif family=="geometric" and geo is not None and glimit and glimit>0:
            features.append({"row":r,"id":str(ident),"geo":geo,"glimit":glimit,"family":"geometric"})
    if not features: raise ValueError("Template contains no usable dimensional measurement rows.")
    # A single underlying physical part for repeatability; distinct manufactured parts for Part Variation.
    true_values={}
    for f in features:
        if "nominal" in f:
            if study=="repeatability":
                true_values[f["row"]]=f["base"]
            else:
                # Draw one part-level offset for each feature; each workbook gets a new draw below.
                true_values[f["row"]]=f["nominal"]
    # Classification limits/scenarios are synthetic test design labels, not standard-derived.
    for i in range(count):
        wb=load_workbook(template)
        ws=wb["Inspection Report"]
        hdr,c=locate_table(ws)
        serial="SYN-REPEATABILITY-001" if study=="repeatability" else f"SYN-PART-{i+1:03d}"
        update_serial(ws,serial)
        update_study_metadata(wb, study, i+1, seed, serial)
        for feature_index, f in enumerate(features):
            r=f["row"]
            if "nominal" in f:
                tol=f["tol"]
                if study=="repeatability":
                    targets={"good":4.0,"mixed":(4.0,14.0,24.0,34.0),"poor":38.0}
                    target=targets[scenario]
                    if isinstance(target,tuple): target=target[i%len(target)]
                    sd=(target/100.0*tol)/6.0
                    value=true_values[r]+rng.gauss(0,sd)
                else:
                    # Component-to-component spread is intentionally distinct from measurement repeatability.
                    spread={"good":0.04,"mixed":0.12,"poor":0.24}[scenario]*tol
                    part_offset = rng.gauss(0,spread)
                    # The mixed demonstration intentionally introduces a small number
                    # of nonconforming parts on selected characteristics so the Pareto
                    # view has meaningful synthetic examples to display.
                    if scenario == "mixed" and feature_index in (2, 5) and i >= int(count * 0.72):
                        part_offset += (0.62 * tol) * (1 if feature_index == 2 else -1)
                    elif scenario == "poor" and i >= int(count * 0.60):
                        part_offset += (0.58 * tol) * (1 if feature_index % 2 == 0 else -1)
                    value=f["nominal"]+part_offset
                ws.cell(r,c["Dimension — Actual"]).value=round(value,6)
                ws.cell(r,c["Dimension — Error"]).value=round(value-f["nominal"],6)
                ws.cell(r,c["Dimension Pass/Fail"]).value="PASS" if f["lower"]<=value<=f["upper"] else "FAIL"
            else:
                # Keep geometric data distinct; create plausible variation around its baseline.
                g=f["geo"]+rng.gauss(0,f["glimit"]*0.035)
                ws.cell(r,c["Geometric Tolerance — Actual"]).value=round(max(0,g),6)
                ws.cell(r,c["Geometric Tolerance — Pass/Fail"]).value="PASS" if g<=f["glimit"] else "FAIL"
        dest=out_dir/f"synthetic_{study}_{i+1:02d}.xlsx"
        wb.save(dest); wb.close()
    wb0.close()
    print(f"Generated {count} {study} workbooks in {out_dir}")
    print(f"Seed: {seed} ({'fixed/reproducible' if seed is not None else 'random'})")
    print("The generated values are synthetic and must not be used for product acceptance.")

def main():
    p=argparse.ArgumentParser(description="Generate separate synthetic CMM study datasets.")
    p.add_argument("--study",choices=["repeatability","part_variation"],required=True)
    p.add_argument("--count",type=int,default=10)
    p.add_argument("--seed",type=int,default=None,help="Use a fixed integer for reproducible data; omit --seed for a fresh random dataset.")
    p.add_argument("--template",default=None)
    p.add_argument("--scenario",choices=["good","mixed","poor"],default="mixed")
    a=p.parse_args()
    if a.count<2: p.error("--count must be at least 2.")
    template=find_template(a.template)
    generate(a.study,a.count,a.seed,template,a.scenario)

if __name__=="__main__": main()
