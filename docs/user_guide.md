# User guide

## Open the hosted application

Open the Streamlit Community Cloud URL published in the repository README. No local Python installation is required for visitors.

## Choose a study

Use the sidebar to choose **Dynamic Repeatability** or **Part Variation**. The app loads the corresponding included synthetic demonstration dataset automatically.

## Upload inspection reports

Choose **Upload Excel workbooks** in the sidebar and select one or more `.xlsx` or `.xlsm` reports. The current parser expects the `Inspection Report` worksheet and the established column headings documented in `core/excel_reader.py`.

Uploads are processed in a temporary directory for the current app session. The public demo is not a production records-management system; do not upload confidential or personal data.

## Download analysis

The repeatability view provides an Excel analysis download. The part-variation view presents descriptive analysis only in this release.
