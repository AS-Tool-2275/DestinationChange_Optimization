# Destination Change Streamlit App

## Files
- `destination_change_streamlit_app.py`
- `destination_change_unified_flow.py`
- `requirements.txt`

## Run locally
```bash
pip install -r requirements.txt
streamlit run destination_change_streamlit_app.py
```

## Notes
- Upload `PlanDetailTimeline.csv`
- Upload one or more `PSW / Production Schedule.csv` files
- Upload one or more `DueDateCalc.xlsx` files
- The app shows detected vendor order from PSW so you can match DueDateCalc upload order
- Main optimization keeps the current SI/SS logic
- A fallback equalization pass is applied for items with zero safety stock (`Average of SS Wk3 = 0`)
