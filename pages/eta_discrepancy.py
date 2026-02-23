# logistics/pages/eta_discrepancy.py
# ---------------------------------------------------------
# ETA Discrepancy (Drag & Drop) — BC vs Import
# - Excel A (BC): columns ['No.', 'Arrival Date']  e.g., 'PO108214', '20/02/2026'
# - Excel B (Import): columns ['BC PO', 'Estimated Arrival']
# Parsing rules for Import 'BC PO':
#   1) '107977/107978/107978' -> multiple POs (same ETA)
#   2) '107977(106897)' -> ignore parentheses content -> keep '107977'
# ---------------------------------------------------------

import io
import re
from datetime import datetime
from typing import List, Optional

import pandas as pd
import streamlit as st


# ---------- Small helper: light CSS to echo your card-like layout ----------
CARD_CSS = """
<style>
.section-title { font-size: 1.25rem; font-weight: 700; margin-top: 1rem; }
.subtle { color: #6b7280; } /* Tailwind gray-500 vibe */
hr { border: 0; border-top: 1px solid #e5e7eb; margin: 1.25rem 0; }
.upload-hint { font-size: 0.9rem; color: #64748b; margin-top: 0.35rem; }
.callout {
  background: #f1f5f9; color: #0f172a; padding: 0.85rem 1rem; border-radius: 8px; border: 1px solid #e2e8f0;
}
.btn-row { margin-top: 0.5rem; }
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)


# ---------- Parsing helpers ----------
def extract_six_digit_from_bc_no(value: str) -> Optional[str]:
    """From BC 'No.' like 'PO108214' return '108214'."""
    if value is None:
        return None
    m = re.search(r"\bPO(\d{6})\b", str(value).strip(), flags=re.IGNORECASE)
    return m.group(1) if m else None


def split_bc_po_value(value: str) -> List[str]:
    """
    Import 'BC PO' parsing rules:
      - Remove parentheses content first: '107977(106897)' -> '107977'
      - If contains '/', split and extract a 6-digit from each piece: '107977/107978/107978'
      - Otherwise extract the first 6-digit from the cleaned string
    Preserve duplicates if present.
    """
    if value is None:
        return []

    text = str(value)
    cleaned = re.sub(r"\([^)]*\)", "", text)  # drop (xxxxxx)

    if "/" in cleaned:
        parts = [p.strip() for p in cleaned.split("/") if p.strip()]
        out: List[str] = []
        for p in parts:
            m = re.search(r"\b(\d{6})\b", p)
            if m:
                out.append(m.group(1))
        return out

    m = re.search(r"\b(\d{6})\b", cleaned)
    return [m.group(1)] if m else []


def load_bc_df(file_bytes: bytes) -> pd.DataFrame:
    """
    Read Excel A (BC) and return: PO_num (6-digit str), bc_date (Timestamp)
    Expect columns ['No.', 'Arrival Date'] and dates like 20/02/2026 (dd/mm/yyyy).
    """
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, engine="openpyxl")

    # Flexible mapping but require those logical names
    colmap = {str(c).strip(): c for c in df.columns}
    key_no = next((c for c in colmap if c.lower() == "no."), None)
    key_arrival = next((c for c in colmap if c.lower() == "arrival date"), None)
    if key_no is None or key_arrival is None:
        raise ValueError(f"BC file must contain 'No.' and 'Arrival Date'. Found columns: {list(df.columns)}")

    out = df[[colmap[key_no], colmap[key_arrival]]].copy()
    out.columns = ["No.", "Arrival Date"]

    out["PO_num"] = out["No."].apply(extract_six_digit_from_bc_no)
    # dayfirst=True to support '20/02/2026'
    out["bc_date"] = pd.to_datetime(out["Arrival Date"], errors="coerce", dayfirst=True).dt.date
    out = out.dropna(subset=["PO_num"]).copy()
    out["bc_date"] = pd.to_datetime(out["bc_date"], errors="coerce")
    return out[["PO_num", "bc_date"]]


def load_import_df(file_bytes: bytes) -> pd.DataFrame:
    """
    Read Excel B (Import) and return: PO_num, imp_date, sheet
    Require columns (case-insensitive): 'BC PO' and 'Estimated Arrival'.
    Apply split_bc_po_value to expand multiple POs for the same ETA.
    Keep LAST occurrence per PO across all sheets.
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

        columns_lower = {str(c).strip().lower(): c for c in df.columns}
        bc_po_key = next((k for k in columns_lower if k == "bc po"), None)
        eta_key   = next((k for k in columns_lower if k == "estimated arrival"), None)
        if bc_po_key is None or eta_key is None:
            # uncomment next two lines to also accept 'ETA Dates'/'ETA Date' as fallback:
            # eta_key = next((k for k in columns_lower if k in ("estimated arrival","eta dates","eta date")), None)
            # if bc_po_key is None or eta_key is None: continue
            continue

        bc_po_col = columns_lower[bc_po_key]
        eta_col   = columns_lower[eta_key]

        for _, r in df[[bc_po_col, eta_col]].iterrows():
            pos = split_bc_po_value(r[bc_po_col])
            if not pos:
                continue
            dt = pd.to_datetime(r[eta_col], errors="coerce", dayfirst=True)
            date_only = pd.to_datetime(dt.date()) if pd.notna(dt) else pd.NaT
            for p in pos:
                rows.append({"PO_num": p, "imp_date": date_only, "sheet": sheet})

    if not rows:
        raise ValueError("Could not find usable 'BC PO' and 'Estimated Arrival' on any sheet.")

    all_rows = pd.DataFrame(rows)
    all_rows["row_order"] = range(len(all_rows))
    latest = (
        all_rows.sort_values("row_order")
        .groupby("PO_num", as_index=False)
        .tail(1)
        .drop(columns=["row_order"])
    )
    return latest[["PO_num", "imp_date", "sheet"]]


def compare(bc_df: pd.DataFrame, imp_df: pd.DataFrame, tolerance_days: int = 0):
    merged = bc_df.merge(imp_df, on="PO_num", how="left")
    merged["day_diff"] = (merged["imp_date"] - merged["bc_date"]).dt.days
    mismatches = merged[
        merged["bc_date"].notna() & merged["imp_date"].notna() & (merged["day_diff"].abs() > tolerance_days)
    ].copy()
    missing = merged[merged["imp_date"].isna()][["PO_num", "bc_date"]].copy()
    return merged, mismatches, missing


def to_excel(mismatches: pd.DataFrame, missing: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as xw:
        mismatches.to_excel(xw, sheet_name="Mismatches", index=False)
        missing.to_excel(xw, sheet_name="Missing_in_ImportDoc", index=False)
    output.seek(0)
    return output.read()


# ---------- Header (to echo your look & feel) ----------
st.markdown(
    """
    <h1 style="display:flex;align-items:center;gap:.6rem;">
      <span style="font-size:2.1rem;">🧭</span>
      <span>ETA DISCREPANCY CHECK</span>
    </h1>
    """,
    unsafe_allow_html=True,
)

# ---------- Upload Card A (BC) ----------
st.markdown('<div class="section-title">BC ETA</div>', unsafe_allow_html=True)
st.caption("Upload Excel A (BC ETA)")
bc_file = st.file_uploader(
    "Drag and drop file here",
    type=["xlsx"],
    key="bc",
    help="Limit 200MB per file • XLSX",
    label_visibility="collapsed",
)
st.markdown('<div class="upload-hint">Limit 200MB per file • XLSX</div>', unsafe_allow_html=True)

# ---------- Upload Card B (Import) ----------
st.markdown('<div class="section-title" style="margin-top:1.25rem;">IMPORT DOC</div>', unsafe_allow_html=True)
st.caption("Upload Excel B (Import Doc)")
imp_file = st.file_uploader(
    "Drag and drop file here",
    type=["xlsx"],
    key="imp",
    help="Limit 200MB per file • XLSX",
    label_visibility="collapsed",
)
st.markdown('<div class="upload-hint">Limit 200MB per file • XLSX</div>', unsafe_allow_html=True)

st.markdown("<hr/>", unsafe_allow_html=True)

# ---------- CTA (disabled until both files present) ----------
run_col = st.container()
with run_col:
    if not bc_file or not imp_file:
        st.markdown(
            '<div class="callout">Upload your BC ETA (Excel A) and Import Document (Excel B) files above to begin.</div>',
            unsafe_allow_html=True,
        )
        st.stop()

# ---------- Controls row ----------
with st.expander("Advanced options", expanded=False):
    tol = st.number_input("Date tolerance (days)", min_value=0, max_value=60, value=0,
                          help="Treat dates within N days as equal (ignored if within tolerance).")

# ---------- Process ----------
with st.spinner("Parsing and comparing …"):
    try:
        bc_df = load_bc_df(bc_file.getvalue())
    except Exception as e:
        st.error(f"❌ Failed to read BC file: {e}")
        st.stop()

    try:
        imp_df = load_import_df(imp_file.getvalue())
    except Exception as e:
        st.error(f"❌ Failed to read Import file: {e}")
        st.stop()

    merged, mismatches, missing = compare(bc_df, imp_df, tolerance_days=tol)

# ---------- Metrics ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("BC POs", f"{len(merged):,}")
c2.metric("Import ETA found", f"{merged['imp_date'].notna().sum():,}")
c3.metric("Mismatches", f"{len(mismatches):,}")
c4.metric("Missing in Import", f"{len(missing):,}")

# ---------- Results ----------
st.markdown("### 🔎 Mismatches")
if mismatches.empty:
    st.success("No mismatches under current tolerance.")
else:
    show_cols = ["PO_num", "bc_date", "imp_date", "day_diff", "sheet"]
    st.dataframe(mismatches[show_cols].sort_values("PO_num"), use_container_width=True, hide_index=True)

st.markdown("### 🕳️ BC POs missing in Import Doc")
if missing.empty:
    st.info("No BC POs are missing in the import workbook.")
else:
    st.dataframe(missing.sort_values("PO_num"), use_container_width=True, hide_index=True)

# ---------- Download ----------
if not mismatches.empty or not missing.empty:
    xls_bytes = to_excel(mismatches, missing)
    st.download_button(
        "⬇️ Download results (Excel)",
        data=xls_bytes,
        file_name=f"po_eta_mismatches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ---------- Friendly footnote ----------
st.caption(
    "Spec: Excel A must have ['No.','Arrival Date'] with 'No.' like 'PO108214'. "
    "Excel B must have ['BC PO','Estimated Arrival']. "
    "BC PO rules: slashes split into multiple POs; numbers in parentheses are ignored. "
    "Dates are parsed with day-first (e.g., 20/02/2026) and compared by date only."
)
