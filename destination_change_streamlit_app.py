
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

import pandas as pd
import streamlit as st

from destination_change_unified_flow import (
    PriorityRule,
    detect_psw_vendors,
    fmt_date,
    load_fwk3_from_production,
    normalize_pct,
    normalize_whse,
    parse_user_date,
    process_files,
    saturday_of_current_week,
)

st.set_page_config(page_title="Destination Change App", layout="wide")

st.title("Destination Change App")
st.caption("Multi-vendor PSW support with Firm PO Reconciliation Gap logic")

with st.expander("Backend logic summary", expanded=False):
    st.markdown(
        """
- **F Wk3 for optimizer** = main vendor PSW `F` at Target Week only.
- **Other Vendor Supply** = explicit other/sub vendor PSW `F` supply when uploaded and matched as other vendor.
- **Firm PO Reconciliation Gap** = Timeline Firm PO at mapped ETA week minus PSW F used for reconciliation.
- **Total Supply Added to SI** = Main Vendor F Wk3 + Other Vendor Supply + Firm PO Reconciliation Gap.
- **New SI** = Current SI + Total Supply Added to SI.
- **New SI-SS** = Current SI-SS + Total Supply Added to SI.
- **SI After** = New SI + Net Destination Change.
- **Sub vendor DC columns** are suggestion-only columns in Optimized Data, calculated after the main-vendor result.
- **Optional OSQP second-pass** can add separate sheets for main-vendor and sub-vendor what-if optimization.
        """
    )
left, right = st.columns([1.2, 0.8])

with left:
    st.subheader("1. Upload input files")
    plan_file = st.file_uploader("PlanDetailTimeline raw CSV", type=["csv"], key="plan")
    psw_files = st.file_uploader(
        "PSW / Production Schedule raw CSV files",
        type=["csv"],
        accept_multiple_files=True,
        key="psw",
        help="Upload one or more PSW/Production Schedule files. The app will detect vendor order from these files and guide DueDateCalc upload order.",
    )
    due_files = st.file_uploader(
        "DueDateCalc Excel files",
        type=["xlsx", "xlsm", "xls"],
        accept_multiple_files=True,
        key="due",
        help="Upload order should follow the vendor order detected from PSW / Production Schedule. If only one file is uploaded, all vendors use the same transit time.",
    )

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

# Live vendor-order preview / instructions
st.subheader("Detected vendor order for DueDateCalc mapping")
if psw_files:
    try:
        with tempfile.TemporaryDirectory() as vendor_tmp:
            preview_psw_paths = []
            for f in psw_files:
                p = Path(vendor_tmp) / Path(f.name).name
                p.write_bytes(f.getvalue())
                preview_psw_paths.append(str(p))
            vendor_preview_df = detect_psw_vendors(preview_psw_paths)

        if not vendor_preview_df.empty:
            st.caption(
                "The table below is detected from PSW / Production Schedule. "
                "Use this order to upload DueDateCalc files in the same sequence."
            )
            display_df = vendor_preview_df[["Vendor Order", "Vendor Code", "Source PSW File Order"]].copy()
            st.dataframe(display_df, width='stretch', hide_index=True)

            mapping_rows = []
            for _, row in display_df.iterrows():
                order_no = int(row["Vendor Order"])
                mapping_rows.append({
                    "DueDateCalc #": order_no,
                    "Vendor Order": order_no,
                    "Instruction": f"Upload DueDateCalc file #{order_no} for Vendor Order #{order_no}",
                })
            st.dataframe(pd.DataFrame(mapping_rows), width='stretch', hide_index=True)

            if due_files:
                due_count = len(due_files)
                vendor_count = len(display_df)
                if due_count == 1 and vendor_count > 1:
                    st.info(f"{vendor_count} vendors detected from PSW. One DueDateCalc uploaded, so all vendors will use the same transit time.")
                elif due_count < vendor_count:
                    st.warning(
                        f"{vendor_count} vendors detected from PSW but only {due_count} DueDateCalc files uploaded. "
                        "The last uploaded DueDateCalc will be used as fallback for remaining vendors."
                    )
                else:
                    st.success("DueDateCalc file count is enough for the detected vendor order.")
        else:
            st.warning("No vendor column/value was detected from PSW. The app will use the first DueDateCalc as default transit time.")
    except Exception as exc:
        st.warning(f"Could not detect vendor order from PSW yet: {exc}")
else:
    st.info("Upload PSW / Production Schedule first so the app can show vendor order for DueDateCalc mapping.")

use_osqp_second_pass = st.checkbox(
    "Add OSQP second-pass sheets optional",
    value=False,
    help="Creates separate what-if sheets for OSQP main-vendor and sub-vendor optimization. The current Optimized Data sheet is kept unchanged.",
)

st.subheader("3. Optional priority rules")
st.write("Leave blank if there are no priority warehouses. `Value`: enter 50 or 0.5 to mean 50%; enter 1 to mean 100%.")
priority_df = st.data_editor(
    pd.DataFrame(columns=["Whse", "Mode", "Value"]),
    num_rows="dynamic",
    width='stretch',
    column_config={
        "Whse": st.column_config.TextColumn("Whse", help="Ví dụ: 335, 5, 1"),
        "Mode": st.column_config.SelectboxColumn("Mode", options=["SI", "SS"], help="SI hoặc SS"),
        "Value": st.column_config.NumberColumn("Value", help="Ví dụ 50 = 50%, 0.5 = 50%"),
    },
)


def build_priority_rules(priority_df: pd.DataFrame) -> Dict[str, PriorityRule]:
    rules: Dict[str, PriorityRule] = {}
    if priority_df is None or priority_df.empty:
        return rules

    for _, row in priority_df.iterrows():
        whse = normalize_whse(row.get("Whse", ""))
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
        rules[whse] = PriorityRule(whse=whse, mode=mode, value=normalize_pct(value_float))
    return rules


def save_uploaded_file(uploaded_file, folder: str, fallback_name: str) -> str:
    suffix = Path(uploaded_file.name or fallback_name).suffix or Path(fallback_name).suffix
    safe_stem = Path(uploaded_file.name or fallback_name).stem.replace(" ", "_")
    path = os.path.join(folder, f"{safe_stem}{suffix}")
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path

st.divider()

run_clicked = st.button("RUN", type="primary", use_container_width=True)

if run_clicked:
    missing = []
    if plan_file is None:
        missing.append("PlanDetailTimeline raw CSV")
    if not psw_files:
        missing.append("PSW / Production Schedule raw CSV files")
    if not due_files:
        missing.append("DueDateCalc Excel files")
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
            psw_paths = [save_uploaded_file(f, tmpdir, f"PSW_{idx+1}.csv") for idx, f in enumerate(psw_files)]
            due_paths = [save_uploaded_file(f, tmpdir, f"DueDateCalc_{idx+1}.xlsx") for idx, f in enumerate(due_files)]
            output_path = os.path.join(tmpdir, output_name)
            priority_rules = build_priority_rules(priority_df)

            progress.progress(20, text="Đang chạy unified flow...")
            final_path = process_files(
                plan_detail_csv=plan_path,
                production_schedule_csv=psw_paths[0],
                due_date_calc_xlsx=due_paths[0],
                output_path=output_path,
                target_week=target_week,
                current_week=current_week,
                priority_rules=priority_rules,
                offset_mode=offset_mode,
                psw_csv_paths=psw_paths,
                other_due_date_calc_xlsx=due_paths[1] if len(due_paths) > 1 else None,
                due_date_calc_xlsx_list=due_paths,
                use_osqp_second_pass=use_osqp_second_pass,
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
                "PSW files": len(psw_files),
                "DueDateCalc files": len(due_files),
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
