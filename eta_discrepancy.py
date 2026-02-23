# logistics/pages/eta_discrepancy.py
# ---------------------------------------------------------
# Streamlit page: BC ETA vs Import ETA discrepancy checker
# Spec (with custom BC PO parsing rules):
#  - File 1 (BC): columns = ["No.", "Arrival Date"]
#       e.g., "PO108214" and "20/02/2026"
#  - File 2 (Import): multi-column; must contain "BC PO" and "Estimated Arrival"
# Parsing rules for "BC PO" (Import):
#   - "107977/107978/107978" -> treat as three POs with the same ETA
#   - "107977(106897)" -> ignore numbers in parentheses, keep only the first 6-digit "107977"
# ---------------------------------------------------------

import io
import re
from datetime import datetime
from typing import List, Optional

import pandas as pd
import streamlit as st


# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(page_title="ETA Discrepancy (Drag & Drop)", page_icon="🧭", layout="wide")
st.title("🧭 ETA Discrepancy (Drag & Drop)")
st.caption(
    "Upload two Excel files: "
    "1) **bc-eta.xlsx** with columns **['No.', 'Arrival Date']**, "
    "2) **import_doc_james (pls use this one).xlsx** containing **['BC PO', 'Estimated Arrival']**. "
    "Matches by 6‑digit PO. Implements special parsing for the 'BC PO' field."
)


# -------------------------
# HELPERS
# -------------------------
def extract_six_digit_po_from_bc_no(value: str) -> Optional[str]:
    """Extract 6-digit PO from BC 'No.' values like 'PO108214'."""
    if value is None:
        return None
    m = re.search(r"\bPO(\d{6})\b", str(value).strip(), flags=re.IGNORECASE)
    return m.group(1) if m else None


def split_bc_po_value(value: str) -> List[str]:
    """
    Parse the 'BC PO' cell according to the custom rules:

    1) '107977/107978/107978'  -> ['107977', '107978', '107978']
    2) '107977(106897)'        -> ['107977']  (ignore numbers in parentheses)
    3) Any parentheses anywhere -> remove their content before processing
    4) If no '/', just extract the first 6-digit number from the cleaned text

    Notes:
    - We only return valid 6-digit numbers.
    - We preserve duplicates if they appear (e.g., '.../107978/107978').
    """
    if value is None:
        return []

    text = str(value)

    # Remove parenthetical content entirely, e.g., "(106897)" -> ""
    # This makes '107977(106897)' -> '107977'
    cleaned = re.sub(r"\([^)]*\)", "", text)

    # If there are slashes, split on '/'
    if "/" in cleaned:
        parts = [p.strip() for p in cleaned.split("/") if p.strip()]
        result: List[str] = []
        for p in parts:
            m = re.search(r"\b(\d{6})\b", p)
            if m:
                result.append(m.group(1))
        return result

    # Otherwise, just take the first 6-digit in the cleaned string
    m = re.search(r"\b(\d{6})\b", cleaned)
    return [m.group(1)] if m else []


def load_bc_df(file_bytes: bytes) -> pd.DataFrame:
    """
    Read the BC file and return DataFrame with:
      PO_num (6-digit string), bc_date (Timestamp date)
    Expect columns: ["No.", "Arrival Date"].
    """
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, engine="openpyxl")
    colmap = {str(c).strip(): c for c in df.columns}

    key_no = next((c for c in colmap if c.lower() == "no."), None)
    key_arrival = next((c for c in colmap if c.lower() == "arrival date"), None)
    if key_no is None or key_arrival is None:
        raise ValueError(
            "BC file must contain columns 'No.' and 'Arrival Date'. "
            f"Found columns: {list(df.columns)}"
        )

    out = df[[colmap[key_no], colmap[key_arrival]]].copy()
    out.columns = ["No.", "Arrival Date"]

    out["PO_num"] = out["No."].apply(extract_six_digit_po_from_bc_no)
    out["bc_date"] = pd.to_datetime(out["Arrival Date"], errors="coerce").dt.date
    out = out.dropna(subset=["PO_num"]).copy()
    out["bc_date"] = pd.to_datetime(out["bc_date"], errors="coerce")
    return out[["PO_num", "bc_date"]]


def load_import_df(file_bytes: bytes) -> pd.DataFrame:
    """
    Read the Import file and return DataFrame with:
      PO_num (6-digit string), imp_date (Timestamp date), sheet
    Must find columns named (case-insensitive match):
      - "BC PO"
      - "Estimated Arrival"
    For each row, we apply 'split_bc_po_value' to possibly yield multiple POs per single row,
    all sharing the same ETA.
    If a PO appears multiple times (across sheets/rows), the **last occurrence** wins.
    """
    xl = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    rows = []

    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet)
        except Exception:
            continue
        if df.empty:
            continue

        # Map to find exact columns by case-insensitive name
        columns_lower = {str(c).strip().lower(): c for c in df.columns}
        bc_po_key = next((k for k in columns_lower if k == "bc po"), None)
        eta_key = next((k for k in columns_lower if k == "estimated arrival"), None)

        if bc_po_key is None or eta_key is None:
            # If you want to be lenient and allow 'ETA Dates' or 'ETA Date', add them here:
            # eta_key = next((k for k in columns_lower if k in ("estimated arrival","eta dates","eta date")), None)
            # and keep the same requirement text above or update the UI copy.
            continue

        bc_po_col = columns_lower[bc_po_key]
        eta_col = columns_lower[eta_key]

        # Iterate each row and expand BC PO into possibly multiple records
        for _, r in df[[bc_po_col, eta_col]].iterrows():
            po_values = split_bc_po_value(r[bc_po_col])
            if not po_values:
                continue
            eta_dt = pd.to_datetime(r[eta_col], errors="coerce")
            eta_date = pd.to_datetime(eta_dt.date()) if pd.notna(eta_dt) else pd.NaT

            for po in po_values:
                rows.append({"PO_num": po, "imp_date": eta_date, "sheet": sheet})

    if not rows:
        raise ValueError(
            "Could not find usable 'BC PO' and 'Estimated Arrival' columns on any sheet "
            "or BC PO values did not contain any 6-digit PO numbers."
        )

    all_rows = pd.DataFrame(rows)
    # Keep last occurrence per PO (later rows overwrite earlier)
    all_rows["row_order"] = range(len(all_rows))
    latest = (
        all_rows.sort_values("row_order")
        .groupby("PO_num", as_index=False)
        .tail(1)
        .drop(columns=["row_order"])
    )

    return latest[["PO_num", "imp_date", "sheet"]]


def compare(bc_df: pd.DataFrame, imp_df: pd.DataFrame, tolerance_days: int = 0):
    """
    Compare by PO_num. Returns:
      merged, mismatches, missing
    """
    merged = bc_df.merge(imp_df, on="PO_num", how="left")
    merged["day_diff"] = (merged["imp_date"] - merged["bc_date"]).dt.days

    mismatches = merged[
        merged["bc_date"].notna()
        & merged["imp_date"].notna()
        & (merged["day_diff"].abs() > tolerance_days)
    ].copy()

    missing = merged[merged["imp_date"].isna()][["PO_num", "bc_date"]].copy()
    return merged, mismatches, missing


def to_excel_bytes(mismatches: pd.DataFrame, missing: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        mismatches.to_excel(writer, sheet_name="Mismatches", index=False)
        missing.to_excel(writer, sheet_name="Missing_in_ImportDoc", index=False)
    output.seek(0)
    return output.read()


# -------------------------
# SIDEBAR CONTROLS
# -------------------------
st.sidebar.header("⚙️ Settings")
tol = st.sidebar.number_input("Date tolerance (days)", min_value=0, max_value=60, value=0)
st.sidebar.caption("Treat dates within N days as equal.")

st.sidebar.markdown("---")
st.sidebar.subheader("Upload files (drag & drop)")
bc_file = st.sidebar.file_uploader(
    "1) Upload bc-eta.xlsx (must have columns ['No.', 'Arrival Date'])", type=["xlsx"], key="bc"
)
imp_file = st.sidebar.file_uploader(
    "2) Upload import_doc_james (pls use this one).xlsx (must include 'BC PO' and 'Estimated Arrival')",
    type=["xlsx"],
    key="imp",
)

st.sidebar.info("Both uploads are required for this page.")


# -------------------------
# MAIN FLOW
# -------------------------
if not bc_file or not imp_file:
    st.warning("Please upload **both** files to proceed.")
    st.stop()

with st.spinner("Parsing files…"):
    try:
        bc_df = load_bc_df(bc_file.getvalue())
    except Exception as e:
        st.error(f"❌ Failed to load BC file: {e}")
        st.stop()

    try:
        imp_df = load_import_df(imp_file.getvalue())
    except Exception as e:
        st.error(f"❌ Failed to load Import file: {e}")
        st.stop()

# Compare
merged, mismatches, missing = compare(bc_df, imp_df, tolerance_days=tol)

# Metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("BC POs", f"{len(merged):,}")
c2.metric("Import ETA found", f"{merged['imp_date'].notna().sum():,}")
c3.metric("Mismatches", f"{len(mismatches):,}")
c4.metric("Missing in Import", f"{len(missing):,}")

st.markdown("---")

# Results
tab1, tab2, tab3 = st.tabs(["🔎 Mismatches", "🕳️ Missing in Import", "🧪 Preview & Validation"])

with tab1:
    st.subheader("🔎 Arrival mismatches (|Import − BC| > tolerance)")
    if mismatches.empty:
        st.success("No mismatches under current tolerance.")
    else:
        show_cols = ["PO_num", "bc_date", "imp_date", "day_diff", "sheet"]
        st.dataframe(mismatches[show_cols].sort_values("PO_num"), use_container_width=True, hide_index=True)
        xls_bytes = to_excel_bytes(mismatches[show_cols], missing)
        st.download_button(
            "⬇️ Download results (Excel)",
            data=xls_bytes,
            file_name=f"po_eta_mismatches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

with tab2:
    st.subheader("🕳️ BC POs missing in Import workbook")
    if missing.empty:
        st.info("No BC POs are missing in the import workbook.")
    else:
        st.dataframe(missing.sort_values("PO_num"), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("🧪 Quick validation preview")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**BC sample (first 10)**")
        st.dataframe(bc_df.head(10), use_container_width=True, hide_index=True)
    with col_b:
        st.markdown("**Import sample (first 10)**")
        st.dataframe(imp_df.head(10), use_container_width=True, hide_index=True)

st.caption(
    "Parsing rules for 'BC PO': slashes split into multiple POs; numbers in parentheses are ignored. "
    "Dates are compared by date only (time ignored)."
)
