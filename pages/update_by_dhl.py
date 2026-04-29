import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from io import BytesIO

# =========================================================
# App config
# =========================================================
st.set_page_config(
    page_title="Shipment → STAGING Update",
    layout="wide"
)

st.title("Shipment Level Report → STAGING.xlsx")

# =========================================================
# Helpers
# =========================================================
ORDER_RE = re.compile(r"\b\d{6}\b")
CREATED_DT_REGEX = re.compile(r"(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})")

def extract_orders(val):
    if pd.isna(val):
        return []
    return list(dict.fromkeys(ORDER_RE.findall(str(val))))

def excel_serial_to_date(val):
    if pd.isna(val):
        return None
    try:
        return (datetime(1899, 12, 30) + timedelta(days=float(val))).date()
    except Exception:
        return None

def parse_eta_any(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return excel_serial_to_date(val)
    try:
        return datetime.strptime(str(val).strip(), "%d/%m/%y").date()
    except Exception:
        try:
            return pd.to_datetime(val).date()
        except Exception:
            return None

# =========================================================
# File upload
# =========================================================
shipment_file = st.file_uploader("Upload Shipment Level Report (.xlsx)", type=["xlsx"])
staging_file = st.file_uploader("Upload STAGING.xlsx", type=["xlsx"])

if not shipment_file or not staging_file:
    st.info("Please upload both files to continue.")
    st.stop()

# =========================================================
# Load Shipment Level Report
# =========================================================
ship_raw = pd.read_excel(shipment_file, header=None)

# Find shipment header row
ship_header = None
for i, row in ship_raw.iterrows():
    text = " ".join(str(x).lower() for x in row if pd.notna(x))
    if "all references" in text and "shipper name" in text:
        ship_header = i
        break

if ship_header is None:
    st.error("Shipment header row not found.")
    st.stop()

ship_df = pd.read_excel(shipment_file, header=ship_header).copy()

# Normalize shipment column names
ship_df.columns = (
    ship_df.columns.astype(str)
    .str.strip()
    .str.replace(r"\s+", " ", regex=True)
)

# =========================================================
# Extract Created date (DHL‑robust, DATE ONLY)
# =========================================================
created_date = None

for r_idx, row in ship_raw.iterrows():
    row_text = " ".join(str(x) for x in row if pd.notna(x))
    if "created" in row_text.lower():
        for cr in range(max(0, r_idx - 2), min(len(ship_raw), r_idx + 4)):
            cr_text = " ".join(str(x) for x in ship_raw.iloc[cr] if pd.notna(x))
            match = CREATED_DT_REGEX.search(cr_text)
            if match:
                created_date = datetime.strptime(
                    match.group(1), "%d.%m.%Y %H:%M"
                ).date()
                break
    if created_date:
        break

if not created_date:
    st.error("Created date not found in shipment report.")
    st.stop()

st.success(f"Shipment report date: {created_date.strftime('%d/%m/%Y')}")

# =========================================================
# Shipment ETA processing (FIXED)
# =========================================================
ship_df["ETA_date"] = ship_df["Estimated Arrival"].apply(parse_eta_any)

ship_df = ship_df[
    ship_df["ETA_date"].notna() &
    (ship_df["ETA_date"] > created_date)
].copy()

ship_df["orders"] = ship_df["All References"].apply(extract_orders)

invalid_refs = ship_df[ship_df["orders"].map(len) == 0]
ship_df = ship_df[ship_df["orders"].map(len) > 0].copy()

# =========================================================
# Load STAGING.xlsx (LATEST SHEET ONLY)
# =========================================================
xls = pd.ExcelFile(staging_file)
sheet_dates = {}

for s in xls.sheet_names:
    try:
        sheet_dates[s] = datetime.strptime(s, "%m.%Y")
    except Exception:
        continue

latest_sheet = max(sheet_dates, key=sheet_dates.get)
st.info(f"Using STAGING sheet: {latest_sheet}")

stg_raw = pd.read_excel(staging_file, sheet_name=latest_sheet, header=None)

# Find staging header
stg_header = None
for i, row in stg_raw.iterrows():
    text = " ".join(str(x).lower() for x in row if pd.notna(x))
    if "supplier" in text and "eta" in text and "container" in text:
        stg_header = i
        break

stg_df = pd.read_excel(
    staging_file,
    sheet_name=latest_sheet,
    header=stg_header
).copy()

# Normalize staging column names
stg_df.columns = (
    stg_df.columns.astype(str)
    .str.strip()
    .str.replace(r"\s+", " ", regex=True)
)

# Parse ETA & orders in staging
stg_df["_ETA_date"] = stg_df["ETA"].apply(parse_eta_any)
stg_df["orders"] = stg_df["bc po"].apply(extract_orders)

# Map staging orders
stg_order_map = {}
for idx, orders in stg_df["orders"].items():
    for o in orders:
        stg_order_map.setdefault(o, []).append(idx)

# =========================================================
# PREVIEW: classify changes (NO WRITES)
# =========================================================
new_orders = []
vessel_changes = []
eta_only_changes = []

for _, ship_row in ship_df.iterrows():
    ship_eta = ship_row["ETA_date"]
    ship_vessel_raw = ship_row.get("Vessel Name (Last Leg)")
    norm_ship_vessel = (
        str(ship_vessel_raw).strip().upper()
        if pd.notna(ship_vessel_raw) else None
    )

    for order in ship_row["orders"]:

        # NEW ORDER
        if order not in stg_order_map:
            new_orders.append({
                "Order": order,
                "Supplier": ship_row.get("Shipper Name"),
                "ETA": ship_eta.strftime("%d/%m/%y"),
                "Discharge Port": ship_row.get("Port of Discharge Code"),
                "Vessel": ship_vessel_raw,
                "Voyage": ship_row.get("Voyage/Flight Number (Last Leg)"),
                "Container": ship_row.get("Container Number"),
            })
            continue

        # EXISTING ORDER
        for idx in stg_order_map[order]:
            stg_eta = stg_df.at[idx, "_ETA_date"]
            stg_vessel_raw = stg_df.at[idx, "Arrival Vessel"]
            norm_stg_vessel = (
                str(stg_vessel_raw).strip().upper()
                if pd.notna(stg_vessel_raw) else None
            )

            vessel_changed = (
                norm_ship_vessel and
                norm_stg_vessel and
                norm_ship_vessel != norm_stg_vessel
            )

            eta_changed = stg_eta != ship_eta

            if vessel_changed:
                vessel_changes.append({
                    "Order": order,
                    "Old Vessel": stg_vessel_raw,
                    "New Vessel": ship_vessel_raw,
                    "ETA": ship_eta.strftime("%d/%m/%y"),
                })

            elif eta_changed:
                eta_only_changes.append({
                    "Order": order,
                    "Old ETA": stg_eta.strftime("%d/%m/%y") if stg_eta else "(blank)",
                    "New ETA": ship_eta.strftime("%d/%m/%y"),
                    "Vessel": stg_vessel_raw,
                })

# =========================================================
# PREVIEW UI (ALWAYS RENDER)
# =========================================================
st.subheader("Preview Changes")

if not new_orders and not vessel_changes and not eta_only_changes:
    st.info(


