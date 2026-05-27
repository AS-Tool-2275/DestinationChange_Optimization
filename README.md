Destination Change Streamlit App

Updated logic:
- Main vendor optimization stays in Optimized Data.
- Sub vendor suggestion starts after main-vendor destination change.
- Sub Vendor SI Before = main-vendor SI After.
- Sub Vendor SI After = Sub Vendor SI Before + Sub Vendor Net Destination Change.
- Optional OSQP sheets keep the same sequence: main vendor first, then sub vendor using OSQP main result as baseline when available.

Run locally:
pip install -r requirements.txt
streamlit run destination_change_streamlit_app.py
