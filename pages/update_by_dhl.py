import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from io import BytesIO

# =========================================================
# App config
# =========================================================
st.set_page_config(page_title="Shipment → STAGING Update", layout="wide")
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
def format_eta_ddmmyy(val):
    d = parse_eta_any(val)
    return d.strftime("%d/%m/%y") if d else ""

stg_df["ETA"] = stg_df["ETA"].apply(format_eta_ddmmyy)

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
# Load shipment report
# =========================================================
ship_raw = pd.read_excel(shipment_file, header=None)

ship_header = None
for i, row in ship_raw.iterrows():
    txt = " ".join(str(x).lower() for x in row if pd.notna(x))
    if "all references" in txt and "shipper name" in txt:
        ship_header = i
        break

if ship_header is None:
    st.error("Shipment header row not found.")
    st.stop()

ship_df = pd.read_excel(shipment_file, header=ship_header).copy()

# Normalize shipment columns
ship_df.columns = ship_df.columns.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

# =========================================================
# Extract Created date (robust)
# =========================================================
created_date = None
for r_idx, row in ship_raw.iterrows():
    row_txt = " ".join(str(x) for x in row if pd.notna(x))
    if "created" in row_txt.lower():
        for cr in range(max(0, r_idx - 2), min(len(ship_raw), r_idx + 4)):
            cr_txt = " ".join(str(x) for x in ship_raw.iloc[cr] if pd.notna(x))
            m = CREATED_DT_REGEX.search(cr_txt)
            if m:
                created_date = datetime.strptime(m.group(1), "%d.%m.%Y %H:%M").date()
                break
    if created_date:
        break

if not created_date:
    st.error("Created date not found.")
    st.stop()

st.success(f"Shipment report date: {created_date.strftime('%d/%m/%Y')}")

# =========================================================
# Shipment ETA handling
# =========================================================
ship_df["ETA_date"] = ship_df["Estimated Arrival"].apply(parse_eta_any)
ship_df = ship_df[ship_df["ETA_date"].notna() & (ship_df["ETA_date"] > created_date)]

ship_df["orders"] = ship_df["All References"].apply(extract_orders)
ship_df = ship_df[ship_df["orders"].map(len) > 0]

# =========================================================
# Load STAGING.xlsx (latest sheet)
# =========================================================
xls = pd.ExcelFile(staging_file)
latest_sheet = max(
    {s: datetime.strptime(s, "%m.%Y") for s in xls.sheet_names if re.match(r"\d{2}\.\d{4}", s)},
    key=lambda x: datetime.strptime(x, "%m.%Y")
)

st.info(f"Using STAGING sheet: {latest_sheet}")

stg_raw = pd.read_excel(staging_file, sheet_name=latest_sheet, header=None)

stg_header = None
for i, row in stg_raw.iterrows():
    txt = " ".join(str(x).lower() for x in row if pd.notna(x))
    if "supplier" in txt and "eta" in txt and "container" in txt:
        stg_header = i
        break

stg_df = pd.read_excel(staging_file, sheet_name=latest_sheet, header=stg_header).copy()
stg_df.columns = stg_df.columns.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

stg_df["_ETA_date"] = stg_df["ETA"].apply(parse_eta_any)
stg_df["orders"] = stg_df["bc po"].apply(extract_orders)

stg_order_map = {}
for idx, orders in stg_df["orders"].items():
    for o in orders:
        stg_order_map.setdefault(o, []).append(idx)

# =========================================================
# Preview logic
# =========================================================
new_orders, vessel_changes, eta_only_changes = [], [], []

for _, ship_row in ship_df.iterrows():
    ship_eta = ship_row["ETA_date"]
    ship_vessel_raw = ship_row.get("Vessel Name (Last Leg)")
    norm_ship_vessel = str(ship_vessel_raw).strip().upper() if pd.notna(ship_vessel_raw) else None

    for order in ship_row["orders"]:
        if order not in stg_order_map:
            new_orders.append({
                "Order": order,
                "Supplier": ship_row.get("Shipper Name"),
                "ETA": ship_eta.strftime("%d/%m/%y"),
                "Vessel": ship_vessel_raw
            })
            continue

        for idx in stg_order_map[order]:
            stg_eta = stg_df.at[idx, "_ETA_date"]
            stg_vessel_raw = stg_df.at[idx, "Arrival Vessel"]
            norm_stg_vessel = str(stg_vessel_raw).strip().upper() if pd.notna(stg_vessel_raw) else None

            if norm_ship_vessel and norm_stg_vessel and norm_ship_vessel != norm_stg_vessel:
                vessel_changes.append({
                    "Order": order,
                    "Old Vessel": stg_vessel_raw,
                    "New Vessel": norm_ship_vessel
                })
            elif stg_eta != ship_eta:
                eta_only_changes.append({
                    "Order": order,
                    "Old ETA": stg_eta.strftime("%d/%m/%y") if stg_eta else "(blank)",
                    "New ETA": ship_eta.strftime("%d/%m/%y")
                })

# =========================================================
# Preview UI
# =========================================================
st.subheader("Preview Changes")

if not new_orders and not vessel_changes and not eta_only_changes:
    st.info("✅ No changes detected.")
else:
    if new_orders:
        st.markdown("### 🆕 New Orders")
        st.dataframe(pd.DataFrame(new_orders))
    if vessel_changes:
        st.markdown("### 🚢 Vessel Changed")
        st.dataframe(pd.DataFrame(vessel_changes))
    if eta_only_changes:
        st.markdown("### 📆 ETA Changed")
        st.dataframe(pd.DataFrame(eta_only_changes))

# =========================================================
# CONFIRM & APPLY ACTIONS
# =========================================================
st.markdown("---")

has_changes = bool(new_orders or vessel_changes or eta_only_changes)

confirm = st.checkbox(
    "✅ I confirm the above changes are correct and want to apply them.",
    disabled=not has_changes
)

if st.button("Apply Changes to STAGING.xlsx", disabled=not confirm):

    # -----------------------------
    # INSERT NEW ORDERS (by ETA order)
    # -----------------------------
    for item in new_orders:
        new_eta = datetime.strptime(item["ETA"], "%d/%m/%y").date()

        # sort existing rows by ETA (blank last)
        sorted_df = stg_df.sort_values(
            by="_ETA_date",
            key=lambda s: s.isna()
        ).reset_index(drop=True)

        # find insert position
        pos = 0
        for i, r in sorted_df.iterrows():
            if r["_ETA_date"] and r["_ETA_date"] <= new_eta:
                pos = i + 1

        new_row = {
            "bc po": item["Order"],
            "Supplier": item["Supplier"],
            "ETA": item["ETA"],
            "Discharge Port": item.get("Discharge Port"),
            "Arrival Vessel": item.get("Vessel"),
            "Arrival Voyage": item.get("Voyage"),
            "Container": item.get("Container"),
        }

        top = sorted_df.iloc[:pos]
        bottom = sorted_df.iloc[pos:]
        stg_df = pd.concat(
            [top, pd.DataFrame([new_row]), bottom],
            ignore_index=True
        )

        # recompute helpers after insert
        stg_df["_ETA_date"] = stg_df["ETA"].apply(parse_eta_any)
        stg_df["orders"] = stg_df["bc po"].apply(extract_orders)

    # -----------------------------
    # APPLY VESSEL NAME UPDATES
    # -----------------------------
    for change in vessel_changes:
        for idx in stg_order_map.get(change["Order"], []):
            stg_df.at[idx, "Arrival Vessel"] = change["New Vessel"]

    # -----------------------------
    # APPLY ETA-ONLY UPDATES
    # -----------------------------
    for change in eta_only_changes:
        for idx in stg_order_map.get(change["Order"], []):
            stg_df.at[idx, "ETA"] = change["New ETA"]

    # -----------------------------
    # SAVE UPDATED FILE
    # -----------------------------
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet in xls.sheet_names:
            if sheet == latest_sheet:
                stg_df.drop(columns=["_ETA_date", "orders"], errors="ignore") \
                      .to_excel(writer, sheet_name=sheet, index=False)
            else:
                pd.read_excel(staging_file, sheet_name=sheet) \
                  .to_excel(writer, sheet_name=sheet, index=False)

    output.seek(0)

    st.download_button(
        "⬇ Download Updated STAGING.xlsx",
        data=output,
        file_name="STAGING_updated.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("✅ Changes applied successfully.")

