# CMM Quality Intelligence Platform

A Streamlit prototype for extracting dimensional inspection records from Excel workbooks and presenting two distinct engineering analyses:

- **Dynamic Repeatability** — repeated measurements of the same physical component.
- **Part Variation** — measurements from different manufactured components.

> **Important:** This is a software-development and portfolio prototype. It is not a certified metrology system, a validated production acceptance system, or an approval for product release. The included data is synthetic. Do not upload employer, customer, drawing, supplier or production-confidential data to this public demonstration.

## Live application

**Streamlit app:** _Add your deployed `https://...streamlit.app` URL here after deployment._

## Features

- Batch Excel workbook extraction and validation.
- Separate dimensional and geometric measurement records.
- Repeatability analysis using the calculation implementation in `core/repeatability.py`.
- Limit-utilisation visualisation with green/yellow/orange/red warning bands.
- Part-to-part descriptive statistics, distributions and out-of-spec Pareto summary.
- Excel export for repeatability results.
- Included synthetic demonstration datasets for both study types.

## Repository layout

```text
cmm-quality-intelligence/
├── app.py
├── requirements.txt
├── generate_synthetic_data.py
├── run_analysis.py                 # Optional local command-line analysis
├── core/
│   ├── __init__.py
│   ├── excel_reader.py
│   └── repeatability.py
├── Data/
│   ├── template.xlsx
│   ├── Repeatability/              # Synthetic demo reports, one component
│   └── Part_Variation/             # Synthetic demo reports, different components
├── tests/
├── docs/
└── .streamlit/config.toml
```

`outputs/` is a local generated-results directory and is excluded from Git. The hosted dashboard calculates from the selected dataset at runtime; it does not depend on pre-existing output CSV files.

## Run locally (development only)

Python 3.11 is recommended for this tested dependency set.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The website starts with the included demonstration dataset. Visitors do not need to run the generator or `run_analysis.py`.

## Regenerate synthetic data (development only)

The repository already includes synthetic datasets. Regeneration is optional.

```bash
python generate_synthetic_data.py --study repeatability --count 10 --seed 20261123 --scenario mixed
python generate_synthetic_data.py --study part_variation --count 25 --seed 20261124 --scenario mixed
```

Available scenarios: `good`, `mixed`, `poor`. Use a fixed `--seed` for reproducibility; omit it for a fresh random dataset. The generator reads `Data/template.xlsx` and writes only to the selected study folder.

## Optional command-line analysis

```bash
python run_analysis.py --study repeatability
python run_analysis.py --study part_variation
```

This is optional. The hosted application does not call this script.

## Deploy on Streamlit Community Cloud

1. Create a **public GitHub repository** and upload the contents of this project to its root.
2. Confirm `app.py` and `requirements.txt` are at the repository root.
3. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) using GitHub and authorize access to the repository.
4. Select **Create app**, choose the repository, branch `main`, and entrypoint `app.py`.
5. Optionally choose an available app subdomain, then deploy.
6. Add the resulting app URL to the **Live application** section above and your CV.

Streamlit Community Cloud deploys from the selected GitHub repository and reflects pushed code changes. See the [official deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Tests

Install development test dependencies and run:

```bash
pip install pytest
pytest -q
```

## Production-use boundary

A public Streamlit Community Cloud deployment is for synthetic demonstration only. A workplace deployment requires explicit employer approval and an environment meeting the organisation's information-security and data-governance requirements. Before production use, the software requires documented verification/validation, controlled configuration and rule profiles, traceability, audit logging, access controls, backup/recovery, change management, and an approved method of receiving CMM exports or connecting to CMM systems. Do not treat dashboard PASS/FAIL output as an authorised product-release decision.
