from pathlib import Path
from tempfile import TemporaryDirectory
import io
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from core.excel_reader import extract_batch, validate_cross_report
from core.repeatability import analyse_dimensional_repeatability

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "Data"
st.set_page_config(page_title="CMM Quality Intelligence", page_icon="📐", layout="wide")

st.markdown("""
<style>
.stApp{background:#101820;color:#edf3f8}
.block-container{max-width:1500px;padding-top:1.5rem}
[data-testid="stMetric"]{background:#1b2733;border:1px solid #344454;padding:16px;border-radius:12px}
[data-testid="stMetricLabel"] p{color:#aebdca!important}
[data-testid="stMetricValue"]{color:#edf3f8!important}
section[data-testid="stSidebar"]{background:#141f29}
div[data-testid="stExpander"]{border:1px solid #344454;border-radius:10px}
</style>
""", unsafe_allow_html=True)

GREEN, YELLOW, ORANGE, RED = "#20b879", "#f2c94c", "#f2994a", "#eb5757"

def dark(fig, height=430):
    fig.update_layout(template="plotly_dark", height=height, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#edf3f8"),
        margin=dict(l=25,r=25,t=60,b=50))
    fig.update_xaxes(gridcolor="#344454")
    fig.update_yaxes(gridcolor="#344454")
    return fig

st.title("CMM Quality Intelligence Platform")
st.caption("Dimensional metrology · Repeatability assessment · Manufacturing variation")
st.info("Portfolio demonstration using synthetic inspection data. This prototype is not a certified measurement or product-acceptance system; approved customer and engineering requirements take precedence.")

with st.sidebar:
    st.header("Study configuration")
    study = st.radio("Select study", ["Dynamic Repeatability", "Part Variation"])
    folder_name = "Repeatability" if study == "Dynamic Repeatability" else "Part_Variation"
    source = st.radio("Data source", ["Built-in demo dataset", "Upload Excel workbooks"])
    near_fraction = st.slider("Near-limit warning threshold", .50, .95, .80, .05)
    st.caption("Reference repeatability limits: Critical 10%, Major 20%, Minor 30%. Confirm the applicable customer revision.")

st.header("1 · Inspection data")
records = row_issues = file_summary = cross_issues = pd.DataFrame()
if source == "Built-in demo dataset":
    folder = DATA / folder_name
    paths = sorted(list(folder.glob("*.xlsx")) + list(folder.glob("*.xlsm"))) if folder.exists() else []
    if paths:
        with st.spinner("Extracting and validating workbooks..."):
            records, row_issues, file_summary = extract_batch(paths)
            cross_issues = validate_cross_report(records)
    else:
        st.warning(f"No demonstration workbooks found in Data/{folder_name}. Check the repository data folders.")
        st.stop()
else:
    uploads = st.file_uploader("Upload inspection workbooks", type=["xlsx","xlsm"], accept_multiple_files=True)
    if not uploads:
        st.info("Upload one or more workbooks to begin.")
        st.stop()
    with TemporaryDirectory() as td:
        paths=[]
        for up in uploads:
            p=Path(td)/Path(up.name).name
            p.write_bytes(up.getvalue())
            paths.append(p)
        with st.spinner("Extracting and validating workbooks..."):
            records,row_issues,file_summary=extract_batch(paths)
            cross_issues=validate_cross_report(records)

if records.empty:
    st.error("No measurement records were extracted. Check the workbook template.")
    st.stop()

serials = records.get("serial_number", pd.Series(dtype=object)).dropna().astype(str).unique()
if study == "Dynamic Repeatability" and len(serials)>1:
    st.error(f"Repeatability dataset contains {len(serials)} different serial numbers. Use repeated runs of one physical component.")
    st.stop()
if study == "Part Variation" and len(serials)<2:
    st.warning("Fewer than two distinct serial numbers found. Confirm each workbook represents a different component.")

dims=records[records.characteristic_type=="dimension"].copy()
geos=records[records.characteristic_type=="geometric"].copy()
st.header("2 · Extraction and validation")
a,b,c,d=st.columns(4)
a.metric("Workbooks",len(file_summary)); b.metric("Successfully read",int((file_summary.status=="read").sum()))
c.metric("Records extracted",len(records)); d.metric("Files failed",int((file_summary.status=="failed").sum()))
issues=len(row_issues)+len(cross_issues)
errors=0
for frame in (row_issues,cross_issues):
    if not frame.empty and "severity" in frame: errors += int((frame.severity=="error").sum())
v1,v2,v3=st.columns(3)
v1.metric("Validation issues",issues); v2.metric("Errors",errors); v3.metric("Warnings",max(0,issues-errors))
with st.expander("Workbook processing details"): st.dataframe(file_summary,use_container_width=True,hide_index=True)
if not row_issues.empty:
    with st.expander("Row-level issues"): st.dataframe(row_issues,use_container_width=True,hide_index=True)
if not cross_issues.empty:
    with st.expander("Cross-report issues"): st.dataframe(cross_issues,use_container_width=True,hide_index=True)
if errors: st.error("Validation errors detected. Resolve them before relying on the analysis.")

st.header("3 · Measurement overview")
x,y,z=st.columns(3)
x.metric("Dimensional records",len(dims)); y.metric("Geometric records",len(geos))
z.metric("Dimensional characteristics",dims.characteristic_key.nunique() if not dims.empty else 0)

if study=="Dynamic Repeatability":
    st.header("4 · Dynamic repeatability")
    results,calc_errors=analyse_dimensional_repeatability(records,near_limit_fraction=near_fraction)
    if not calc_errors.empty:
        with st.expander("Characteristics not analysed",expanded=True): st.dataframe(calc_errors,use_container_width=True)
    if results.empty: st.warning("No dimensional characteristics could be analysed."); st.stop()
    results=results.copy()
    results["limit_utilisation_pct"]=results.repeatability_pct/results.acceptance_limit_pct*100
    passed=int((results.acceptance_status=="PASS").sum())
    failed=int((results.acceptance_status=="FAIL").sum())
    near=int((results.warning_status=="NEAR_LIMIT").sum())
    k1,k2,k3,k4=st.columns(4)
    k1.metric("Characteristics analysed",len(results)); k2.metric("PASS",passed); k3.metric("FAIL",failed); k4.metric("Near-limit warnings",near)
    st.subheader("Repeatability limit utilisation")
    st.caption("Utilisation = repeatability percentage ÷ applicable classification limit. 100% is the acceptance boundary.")
    plot=results.sort_values("limit_utilisation_pct")
    fig=go.Figure(go.Bar(x=plot.limit_utilisation_pct,y=plot.characteristic_key,orientation="h",
        marker=dict(color=plot.limit_utilisation_pct,colorscale=[[0,GREEN],[.6,YELLOW],[.8,ORANGE],[1,RED]],cmin=0,cmax=100,
                    colorbar=dict(title="Limit used (%)")),
        customdata=np.stack([plot.repeatability_pct,plot.acceptance_limit_pct,plot.acceptance_status],axis=-1),
        hovertemplate="<b>%{y}</b><br>Limit used %{x:.1f}%<br>Repeatability %{customdata[0]:.2f}%<br>Limit %{customdata[1]:.1f}%<br>Status %{customdata[2]}<extra></extra>"))
    fig.add_vline(x=100,line_dash="dash",line_color=RED,annotation_text="Acceptance limit")
    fig.update_layout(xaxis_title="Applicable acceptance limit used (%)",yaxis_title="",height=max(420,27*len(plot)))
    st.plotly_chart(dark(fig,max(420,27*len(plot))),use_container_width=True)
    st.subheader("Characteristic results")
    cols=["characteristic_key","identifier","classification","number_of_runs","mean","sample_standard_deviation",
          "repeatability_pct","acceptance_limit_pct","limit_utilisation_pct","acceptance_status","warning_status"]
    st.dataframe(results[cols].sort_values("limit_utilisation_pct",ascending=False),use_container_width=True,hide_index=True)
    key=st.selectbox("Inspect an individual characteristic",results.characteristic_key.tolist())
    selected=dims[dims.characteristic_key==key].copy()
    selected["run_number"]=np.arange(1,len(selected)+1)
    line=px.line(selected,x="run_number",y="actual",markers=True,labels={"run_number":"Measurement run","actual":"Measured value"})
    line.update_layout(title=f"Measurement sequence · {key}")
    st.plotly_chart(dark(line,350),use_container_width=True)
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        results.to_excel(writer,sheet_name="Repeatability Results",index=False)
        calc_errors.to_excel(writer,sheet_name="Calculation Errors",index=False)
        row_issues.to_excel(writer,sheet_name="Extraction Issues",index=False)
        cross_issues.to_excel(writer,sheet_name="Cross-report Issues",index=False)
    st.download_button("Download repeatability analysis (Excel)",out.getvalue(),"cmm_repeatability_analysis.xlsx")
else:
    st.header("4 · Part variation")
    st.warning("This study describes variation between manufactured components. Repeatability acceptance limits are not applied.")
    if dims.empty: st.warning("No dimensional measurements available."); st.stop()
    summary=dims.groupby("characteristic_key").agg(identifier=("identifier","first"),n_readings=("actual","count"),
        mean_actual=("actual","mean"),sd=("actual","std"),minimum=("actual","min"),maximum=("actual","max"),
        nominal=("nominal","first"),lsl=("lower_spec_limit","first"),usl=("upper_spec_limit","first")).reset_index()
    summary["observed_spread"]=summary.maximum-summary.minimum
    out_flags=dims.assign(out=(dims.actual<dims.lower_spec_limit)|(dims.actual>dims.upper_spec_limit))
    counts=out_flags.groupby("characteristic_key").out.sum()
    summary["out_of_spec_count"]=summary.characteristic_key.map(counts).fillna(0).astype(int)
    summary["out_of_spec_pct"]=summary.out_of_spec_count/summary.n_readings*100
    p1,p2,p3,p4=st.columns(4)
    p1.metric("Workbooks / components",int(dims.source_file.nunique()))
    p2.metric("Characteristics",len(summary)); p3.metric("Out-of-spec readings",int(summary.out_of_spec_count.sum()))
    p4.metric("Characteristics with failures",int((summary.out_of_spec_count>0).sum()))
    key=st.selectbox("Select a characteristic",summary.characteristic_key.tolist())
    selected=dims[dims.characteristic_key==key].copy()
    spec=summary[summary.characteristic_key==key].iloc[0]
    st.subheader(f"Measurement distribution · {key}")
    hist=px.histogram(selected,x="actual",nbins=18,marginal="box",labels={"actual":"Measured dimension"})
    hist.add_vline(x=spec.lsl,line_dash="dash",line_color=RED,annotation_text="LSL")
    hist.add_vline(x=spec.usl,line_dash="dash",line_color=RED,annotation_text="USL")
    st.plotly_chart(dark(hist,390),use_container_width=True)
    st.subheader("Spread by characteristic")
    ordered=summary.sort_values("observed_spread")
    bar=px.bar(ordered,x="observed_spread",y="characteristic_key",orientation="h",color="out_of_spec_pct",
        color_continuous_scale=[GREEN,YELLOW,ORANGE,RED],
        labels={"observed_spread":"Observed spread","characteristic_key":"Characteristic","out_of_spec_pct":"Out-of-spec (%)"})
    st.plotly_chart(dark(bar,max(420,27*len(ordered))),use_container_width=True)
    st.subheader("Quality Pareto · out-of-spec readings")
    pareto=summary[summary.out_of_spec_count>0].sort_values("out_of_spec_count",ascending=False).copy()
    if pareto.empty: st.success("No out-of-spec readings were identified.")
    else:
        pareto["cumulative_pct"]=pareto.out_of_spec_count.cumsum()/pareto.out_of_spec_count.sum()*100
        fig=go.Figure()
        fig.add_bar(x=pareto.characteristic_key,y=pareto.out_of_spec_count,name="Out-of-spec readings",marker_color=RED)
        fig.add_scatter(x=pareto.characteristic_key,y=pareto.cumulative_pct,name="Cumulative %",yaxis="y2",
                        mode="lines+markers",line=dict(color=YELLOW,width=3))
        fig.update_layout(yaxis=dict(title="Out-of-spec readings"),yaxis2=dict(title="Cumulative (%)",overlaying="y",side="right",range=[0,105]))
        st.plotly_chart(dark(fig,420),use_container_width=True)
    st.subheader("Characteristic summary")
    st.dataframe(summary.sort_values(["out_of_spec_count","observed_spread"],ascending=False),use_container_width=True,hide_index=True)
    st.caption("Descriptive variation only. Cp/Cpk and control-chart conclusions are not calculated in this version.")

if not geos.empty:
    with st.expander("Geometric tolerance records · separate methodology"):
        st.dataframe(geos[["source_file","characteristic_key","identifier","geometric_actual","geometric_limit","geometric_pass_fail"]],use_container_width=True,hide_index=True)
st.divider()
st.caption("CMM Quality Intelligence · Prototype · Verify engineering decisions against approved procedures and customer requirements.")
