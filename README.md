# Destination Change Streamlit Package

## Files
- destination_change_streamlit_app.py
- destination_change_unified_flow.py
- requirements.txt

## What this version does
- Keeps PSW-based vendor-aware DueDateCalc mapping.
- Keeps the zero-SS fallback equalization pass in the backend.
- Uses the main vendor PSW `F` at Target Week for optimizer allocation.
- Keeps optional sub-vendor suggestion columns and optional OSQP second-pass sheets.

## Run locally
```bash
pip install -r requirements.txt
streamlit run destination_change_streamlit_app.py
```

## Notes
- Upload `PlanDetailTimeline.csv`
- Upload one or more `PSW / Production Schedule.csv` files
- Upload one or more `DueDateCalc.xlsx` files in vendor order
- Use the optional priority rules table if needed
