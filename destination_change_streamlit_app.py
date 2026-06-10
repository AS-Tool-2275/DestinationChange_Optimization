"""
Destination Change Unified Flow - Streamlit App

How to run:
  pip install streamlit pandas openpyxl
  streamlit run destination_change_streamlit_app.py

This app requires destination_change_unified_flow.py in the same folder.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict

import pandas as pd
import streamlit as st

from destination_change_unified_flow import (
    PriorityRule,
    fmt_date,
    process_files,
    saturday_of_current_week,
)


st.set_page_config(
    page_title="Destination Change Unified Flow",
    page_icon="📦",
    layout="wide",
)


def save_uploaded_file(uploaded_file, folder: str, fallback_name: str) -> str:
    suffix = Path(uploaded_file.name or fallback_name).suffix or Path(fallback_name).suffix
    safe_stem = Path(uploaded_file.name or fallback_name).stem.replace(" ", "_")
    path = os.path.join(folder, f"{safe_stem}{suffix}")
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path


def build_priority_rules(priority_df: pd.DataFrame) -> Dict[str, PriorityRule]:
    rules: Dict[str, PriorityRule] = {}
    if priority_df is None or priority_df.empty:
        return rules

    for _, row in priority_df.iterrows():
        whse = str(row.get("Whse", "")).strip().upper()
        mode = str(row.get("Mode", "")).strip().upper()
        value = row.get("Value", None)
        if not whse or mode not in {"SI", "SS"}:
            continue
        try:
            value_float = float(value)
        except Exception:
            continue
        if value_float > 1:
            value_float = value_float / 100.0
        rules[whse] = PriorityRule(whse=whse, mode=mode, value=value_float)
    return rules


def render_help():
    with st.expander("Logic tóm tắt", expanded=False):
        st.markdown(
            """
**Input bắt buộc**

1. `PlanDetailTimeline.csv` raw, chưa bỏ 6 dòng đầu.  
2. `Production Schedule.csv` raw. `F Wk3` chỉ lấy dòng `S/F/P = F`, group theo `Item # + Whse`, lấy đúng cột tuần user chọn.  
3. `DueDateCalc.xlsx`. Mặc định dùng `legacy_compatible` để giữ offset giống flow hiện tại.

**Optimizer input mới**

- `New SI = current SI + F Wk3`
- `New SI-SS = current SI-SS + F Wk3`
- Optimizer dùng `New SI` cho bước allocation tiếp theo.

**Output**

File Excel cuối cùng chỉ có sheet `Optimized Data`.
"""
        )


st.title("Destination Change Unified Flow")
st.caption("PlanDetailTimeline + Production Schedule + DueDateCalc → Optimized output")
render_help()

left, right = st.columns([1.2, 0.8])

with left:
    st.subheader("1) Upload input files")
    plan_file = st.file_uploader("PlanDetailTimeline raw CSV", type=["csv"], key="plan")
    production_file = st.file_uploader("Production Schedule raw CSV", type=["csv"], key="production")
    due_file = st.file_uploader("DueDateCalc Excel", type=["xlsx", "xlsm", "xls"], key="due")

with right:
    st.subheader("2) Week setup")
    default_current = saturday_of_current_week()
    default_target = default_current + timedelta(days=14)
    target_week = st.date_input("Target Week / Wk3", value=default_target, format="MM/DD/YYYY")
    current_week = st.date_input("Current Week", value=default_current, format="MM/DD/YYYY")
    offset_mode = st.selectbox(
        "DueDate offset mode",
        options=["legacy_compatible", "due_date"],
        index=0,
        help="legacy_compatible giữ logic giống SI-SS_WANEK 3.py. due_date dùng ceil(Delivery Days / 7).",
    )
    output_name = st.text_input(
        "Output file name",
        value=f"destination_change_unified_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
    )

st.subheader("3) Priority rules optional")
st.write("Để trống nếu không có kho ưu tiên. `Value`: nhập 50 hoặc 0.5 đều được hiểu là 50%; nhập 1 được hiểu là 100%.")
priority_df = st.data_editor(
    pd.DataFrame(columns=["Whse", "Mode", "Value"]),
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Whse": st.column_config.TextColumn("Whse", help="Ví dụ: 335, 5, 1"),
        "Mode": st.column_config.SelectboxColumn("Mode", options=["SI", "SS"], help="SI hoặc SS"),
        "Value": st.column_config.NumberColumn("Value", help="Ví dụ 50 = 50%, 0.5 = 50%"),
    },
)

run_clicked = st.button("RUN", type="primary", use_container_width=True)

if run_clicked:
    missing = []
    if plan_file is None:
        missing.append("PlanDetailTimeline raw CSV")
    if production_file is None:
        missing.append("Production Schedule raw CSV")
    if due_file is None:
        missing.append("DueDateCalc Excel")
    if missing:
        st.error("Thiếu file input: " + ", ".join(missing))
        st.stop()

    if current_week > target_week:
        st.error("Current Week không được lớn hơn Target Week.")
        st.stop()

    if not output_name.lower().endswith(".xlsx"):
        output_name += ".xlsx"

    progress = st.progress(0, text="Đang chuẩn bị file...")
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            plan_path = save_uploaded_file(plan_file, tmpdir, "PlanDetailTimeline.csv")
            production_path = save_uploaded_file(production_file, tmpdir, "ProductionSchedule.csv")
            due_path = save_uploaded_file(due_file, tmpdir, "DueDateCalc.xlsx")
            output_path = os.path.join(tmpdir, output_name)
            priority_rules = build_priority_rules(priority_df)

            progress.progress(15, text="Đang chạy unified flow...")
            final_path = process_files(
                plan_detail_csv=plan_path,
                production_schedule_csv=production_path,
                due_date_calc_xlsx=due_path,
                output_path=output_path,
                target_week=target_week,
                current_week=current_week,
                priority_rules=priority_rules,
                offset_mode=offset_mode,
            )
            progress.progress(90, text="Đang tạo download file...")

            with open(final_path, "rb") as f:
                output_bytes = f.read()

            st.session_state["last_output_bytes"] = output_bytes
            st.session_state["last_output_name"] = Path(final_path).name
            st.session_state["last_run_info"] = {
                "Target Week": fmt_date(target_week),
                "Current Week": fmt_date(current_week),
                "Offset mode": offset_mode,
                "Priority rules": len(priority_rules),
            }
            progress.progress(100, text="Hoàn tất")
            st.success("Đã tạo output thành công.")

        except Exception as exc:
            progress.empty()
            st.error(f"Có lỗi khi xử lý: {exc}")
            st.stop()

if "last_output_bytes" in st.session_state:
    st.subheader("Download output")
    st.download_button(
        label="Download optimized Excel",
        data=st.session_state["last_output_bytes"],
        file_name=st.session_state.get("last_output_name", "destination_change_output.xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    with st.expander("Run info", expanded=True):
        st.json(st.session_state.get("last_run_info", {}))
