# Destination Change Streamlit Package

## Files
- `destination_change_streamlit_app.py`
- `destination_change_unified_flow.py`
- `requirements.txt`

## What changed
- PSW / Production Schedule upload now drives a live vendor-order preview for DueDateCalc upload order.
- DueDateCalc upload guidance is shown in the UI as soon as PSW files are uploaded.
- If only one DueDateCalc is uploaded, all vendors use the same transit time.
- If DueDateCalc files are fewer than detected vendors, the last file is used as fallback.
- Added a fallback equalization pass for `Average of SS Wk3 = 0` warehouses.

## Run locally
```bash
pip install -r requirements.txt
streamlit run destination_change_streamlit_app.py
```
