# Destination Change Streamlit App

Run locally:

```bash
pip install -r requirements.txt
streamlit run destination_change_streamlit_app.py
```

Update included:
- Detect vendor order from PlanDetailTimeline.
- Show vendor count/order in Streamlit.
- DueDateCalc upload order follows detected vendor order.
- If one DueDateCalc is uploaded, all vendors use the same transit time.
- If fewer DueDateCalc files than detected vendors are uploaded, the last uploaded file is used as fallback.
