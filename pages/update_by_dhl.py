import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from io import BytesIO

import streamlit as st
st.warning("✅ RUNNING UPDATED CODE VERSION (Created-date fix enabled)")

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

def extract_orders(val):
    """Extract unique 6‑digit order numbers from any string."""
    if pd.isna(val):
        return []
    return list(dict.fromkeys(ORDER_RE.findall(str(val))))

def excel_serial_to_date(val):
    """Convert Excel serial date to date (DATE ONLY)."""
    if pd.isna(val):
        return None
    try:
        return (datetime(1899, 12, 30) + timedelta(days=float(val))).date()
    except Exception:
        return None

def parse_eta_any(val):
    """Parse ETA from serial or dd/mm/yy string into date."""
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
shipment_file = st.file_uploader(
    "Upload Shipment Level Report (.xlsx)", type=["xlsx"]
)
staging_file = st.file_uploader(
    "Upload STAGING.xlsx", type=["xlsx"]
)

if not shipment_file or not staging_file:
    st.info("Please upload both files to continue.")
    st.stop()

# =========================================================
# Load Shipment Level Report
# =========================================================
ship_raw = pd.read_excel(shipment_file, header=None)

# Find header row
ship_header = None
for i, row in ship_raw.iterrows():
    text = " ".join(str(x).lower() for x in row if pd.notna(x))
    if "all references" in text and "shipper name" in text:
        ship_header = i
        break

if ship_header is None:
    st.error("Shipment header row not found.")
    st.stop()

ship_df = pd.read_excel(shipment_file, header=ship_header)


# Extract Created date (DATE ONLY)

# =========================================================
# Extract Created date (DEBUG MODE)
# =========================================================
CREATED_DT_REGEX = re.compile(
    r"(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})"
)

created_date = None

st.write("🔍 Scanning Shipment Level Report for Created date...")

for r_idx, row in ship_raw.iterrows():
    row_text = " ".join(str(x) for x in row if pd.notna(x))

    if "created" in row_text.lower():
        st.write(f"➡ Found 'Created' near row {r_idx}:")
        st.write(row_text)

        for check_row in range(max(0, r_idx - 2), min(len(ship_raw), r_idx + 4)):
            check_text = " ".join(
                str(x) for x in ship_raw.iloc[check_row] if pd.notna(x)
            )
            match = CREATED_DT_REGEX.search(check_text)

            if match:
                ts = match.group(1)
                st.write(f"✅ Found datetime candidate in row {check_row}: {ts}")

                try:
                    created_date = datetime.strptime(ts, "%d.%m.%Y %H:%M").date()
                    st.success(f"✅ Parsed created_date = {created_date}")
                    break
                except Exception as e:
                    st.error(f"❌ Failed parsing datetime: {ts}")
                    st.exception(e)

    if created_date:
        break

if not created_date:
    st.error("❌ Created date STILL not found. See debug output above.")
    st.stop()



# ETA handling (DATE ONLY) and filter
ship_df["ETA_date"] = ship_df["Estimated Arrival"].apply(excel_serial_to_date)
ship_df = ship_df[
    ship_df["ETA_date"].notna() &
    (ship_df["ETA_date"] > created_date)
].copy()

# Extract orders
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

if not sheet_dates:
    st.error("No date-based sheets found in STAGING.xlsx.")
    st.stop()

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

if stg_header is None:
    st.error("Staging header row not found.")
    st.stop()

stg_df = pd.read_excel(
    staging_file,
    sheet_name=latest_sheet,
    header=stg_header
).copy()

stg_df.columns = [c.strip() for c in stg_df.columns]

# Mandatory columns
lower_cols = [c.lower() for c in stg_df.columns]
for col in ["bc po", "arrival vessel", "eta"]:
    if col not in lower_cols:
        st.error(f"Mandatory column missing in STAGING: {col}")
        st.stop()

# Normalise ETA and orders in staging
stg_df["_ETA_date"] = stg_df["ETA"].apply(parse_eta_any)
stg_df["orders"] = stg_df["bc po"].apply(extract_orders)

# Map staging orders to row indices
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
    for order in ship_row["orders"]:

        ship_eta = ship_row["ETA_date"]
        ship_vessel = ship_row.get("Vessel Name (Last Leg)")

        # -------- NEW ORDER --------
        if order not in stg_order_map:
            new_orders.append({
                "Order": order,
                "Supplier": ship_row.get("Shipper Name"),
                "ETA": ship_eta.strftime("%d/%m/%y"),
                "Discharge Port": ship_row.get("Port of Discharge Code"),
                "Vessel": ship_vessel,
                "Voyage": ship_row.get("Voyage/Flight Number (Last Leg)"),
                "Container": ship_row.get("Container Number"),
            })
            continue

        # -------- EXISTING ORDER --------
        for idx in stg_order_map[order]:
            stg_eta = stg_df.at[idx, "_ETA_date"]
            stg_vessel = stg_df.at[idx, "Arrival Vessel"]

            vessel_changed = pd.notna(ship_vessel) and stg_vessel != ship_vessel
