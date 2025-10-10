import streamlit as st
import pandas as pd
import re
from io import BytesIO
import datetime

st.set_page_config(page_title="BURNARD SHIPMENT CHECK LIST", layout="wide")
st.title("📦 BURNARD SHIPMENT CHECK LIST")

# File upload
file_a = st.file_uploader("Upload Excel A (Client Order Followup Status Summary Report)", type=["xlsx"], key="file_a")
file_b = st.file_uploader("Upload Excel B (Import Doc)", type=["xlsx"], key="file_b")

# Function to detect header row
def detect_header_row(df, keywords):
    for i in range(min(20, len(df))):
        row = df.iloc[i].astype(str).str.strip().tolist()
        if all(keyword in row for keyword in keywords):
            return i
    return None

# Extract 6-digit PO numbers
def extract_po_numbers(order_value):
    if pd.isna(order_value):
        return []
    return re.findall(r"\b\d{6}\b", str(order_value))

# Normalize ETA to date only
def normalize_eta(val):
    if pd.isna(val) or val == "" or val is None:
        return None
    try:
        dt = pd.to_datetime(val)
        return dt.date()
    except:
        return None

# Format ETA for display - date only without time
def format_eta_display(eta_value):
    if pd.isna(eta_value) or eta_value == "" or eta_value is None:
        return ""
    try:
        # Try to parse as datetime and return date only
        dt = pd.to_datetime(eta_value)
        return dt.strftime("%Y-%m-%d")
    except:
        # Return original if can't parse
        return str(eta_value)

# Normalize Arrival Vessel: remove all spaces and trim
def normalize_vessel(val):
    if pd.isna(val) or val == "" or val is None:
        return ""
    return re.sub(r"\s+", "", str(val)).strip()

# Normalize Arrival Voyage: remove leading 0 and trailing letters
def normalize_voyage(val):
    if pd.isna(val) or val == "" or val is None:
        return ""
    val = str(val).strip()
    digits = re.findall(r"\d+", val)
    if digits:
        num = digits[0].lstrip("0")
        return num
    return ""

# Extract container numbers with type
def extract_container_info(container_value):
    if pd.isna(container_value) or container_value == "" or container_value is None:
        return {"display": ""}
    
    container_str = str(container_value).strip()
    return {"display": container_str}

# Get display value for any column
def get_display_value(value, col_name):
    if pd.isna(value) or value == "" or value is None:
        return ""
    
    if col_name == "ETA":
        return format_eta_display(value)
    elif col_name == "Container":
        container_info = extract_container_info(value)
        return container_info["display"]
    else:
        return str(value)

# Updated compare_rows function to properly handle empty values
def compare_rows(row_a, row_b, columns_to_compare):
    differences = {}
    
    for col in columns_to_compare:
        val_a = row_a.get(col, "")
        val_b = row_b.get(col, "")

        # Get display values for both A and B
        display_a = get_display_value(val_a, col)
        display_b = get_display_value(val_b, col)

        if col == "ETA":
            date_a = normalize_eta(val_a)
            date_b = normalize_eta(val_b)
            # Consider it a difference if one has date and other doesn't, or dates are different
            if date_a != date_b:
                differences[col] = {"Excel A": display_a, "Excel B": display_b}
                
        elif col == "Container":
            # Consider it a difference if display values are different
            if display_a != display_b:
                differences[col] = {
                    "Excel A": display_a,
                    "Excel B": display_b
                }
                
        elif col == "Arrival Vessel":
            norm_a = normalize_vessel(val_a)
            norm_b = normalize_vessel(val_b)
            if norm_a != norm_b:
                differences[col] = {"Excel A": display_a, "Excel B": display_b}
                
        elif col == "Arrival Voyage":
            norm_a = normalize_voyage(val_a)
            norm_b = normalize_voyage(val_b)
            if norm_a != norm_b:
                differences[col] = {"Excel A": display_a, "Excel B": display_b}
                
        else:
            if str(val_a).strip() != str(val_b).strip():
                differences[col] = {"Excel A": display_a, "Excel B": display_b}
    
    # Apply comparison behavior rules
    has_eta_diff = "ETA" in differences
    has_container_diff = "Container" in differences
    
    # Filter differences based on rules
    filtered_differences = {}
    
    if has_eta_diff and not has_container_diff:
        # Only ETA differences → show only ETA
        filtered_differences = {"ETA": differences["ETA"]}
    elif has_container_diff and not has_eta_diff:
        # Only Container differences → show only Container
        filtered_differences = {"Container": differences["Container"]}
    elif has_eta_diff and has_container_diff:
        # Both differ → show both ETA and Container
        filtered_differences = {
            "ETA": differences["ETA"],
            "Container": differences["Container"]
        }
    # If only Arrival Vessel/Voyage differences but no ETA/Container, show nothing
    
    return filtered_differences

# Convert data to CSV for download
def convert_to_csv(data, columns=None):
    output = BytesIO()
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(data, columns=columns)
    df.to_csv(output, index=False)
    return output.getvalue()

# Main logic
if file_a and file_b:
    df_a_raw = pd.read_excel(file_a, sheet_name=0, header=None, engine="openpyxl")

    # Load Excel B with logic to select the most recent sheet based on MM.YYYY format
    sheet_names_b = pd.ExcelFile(file_b).sheet_names
    latest_date = None
    latest_sheet = None

    for sheet in sheet_names_b:
        try:
            date_obj = datetime.datetime.strptime(sheet, "%m.%Y")
            if latest_date is None or date_obj > latest_date:
                latest_date = date_obj
                latest_sheet = sheet
        except ValueError:
            continue

    if latest_sheet:
        df_b = pd.read_excel(file_b, sheet_name=latest_sheet, engine="openpyxl")
        st.info(f"Using the most recent sheet: {latest_sheet}")
    else:
        last_sheet = sheet_names_b[-1]
        df_b = pd.read_excel(file_b, sheet_name=last_sheet, engine="openpyxl")
        st.info(f"Using the last sheet: {last_sheet}")

    # Map Excel B column names to standard names
    existing_columns = df_b.columns.tolist()
    st.write("📋 Excel B Columns Found:", existing_columns)

    # Create mapping for Excel B columns
    column_mapping = {}
    
    # Find and map each required column
    for col in existing_columns:
        col_lower = str(col).lower().strip()
        
        if 'bc po' in col_lower or 'bcpo' in col_lower or 'po' in col_lower:
            column_mapping[col] = "BC PO"
        elif 'estimated arrival' in col_lower or 'eta' in col_lower:
            column_mapping[col] = "ETA"
        elif 'container' in col_lower:
            column_mapping[col] = "Container"
        elif 'arrival vessel' in col_lower or 'vessel' in col_lower:
            column_mapping[col] = "Arrival Vessel"
        elif 'arrival voyage' in col_lower or 'voyage' in col_lower:
            column_mapping[col] = "Arrival Voyage"
        elif 'supplier' in col_lower:
            column_mapping[col] = "Supplier"

    # Rename columns in Excel B
    df_b_renamed = df_b.rename(columns=column_mapping)
    
    # Select only the columns we need
    required_columns = ["BC PO", "Supplier", "ETA", "Container", "Arrival Vessel", "Arrival Voyage"]
    available_columns = [col for col in required_columns if col in df_b_renamed.columns]
    
    if not available_columns:
        st.error("No required columns found in Excel B after mapping.")
        st.stop()
    
    df_b_final = df_b_renamed[available_columns]
    
    st.success(f"✅ Successfully mapped Excel B columns: {available_columns}")

    # Detect header row in Excel A
    header_keywords = ["Order #", "Supplier"]
    header_row_index = detect_header_row(df_a_raw, header_keywords)

    if header_row_index is None:
        st.error("Could not detect header row in Excel A.")
    else:
        df_a = pd.read_excel(file_a, sheet_name=0, header=header_row_index, engine="openpyxl")

        # Clean Excel A: remove rows with invalid ETA
        df_a["ETA"] = pd.to_datetime(df_a["ETA"], errors="coerce")
        df_a_clean = df_a.dropna(subset=["ETA"])

        # Extract PO numbers from Excel A
        po_map_a = {}
        for idx, row in df_a_clean.iterrows():
            po_list = extract_po_numbers(row["Order #"])
            for po in po_list:
                po_map_a[po] = row

        # Extract PO numbers from Excel B
        po_set_b = set()
        if "BC PO" in df_b_final.columns:
            for val in df_b_final["BC PO"]:
                po_set_b.update(extract_po_numbers(val))
        else:
            st.error("Column 'BC PO' not found in Excel B after mapping.")

        # Show sample data from both files
        st.subheader("📊 Sample Data Preview")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("Excel A Sample (3 rows):")
            st.dataframe(df_a_clean[["Order #", "ETA", "Container"]].head(3) if "Container" in df_a_clean.columns else df_a_clean[["Order #", "ETA"]].head(3))
        
        with col2:
            st.write("Excel B Sample (3 rows):")
            st.dataframe(df_b_final.head(3))

        matched_differences = []
        unmatched_pos = []

        columns_to_compare = ["ETA", "Container", "Arrival Vessel", "Arrival Voyage"]

        for po, row_a in po_map_a.items():
            if po in po_set_b:
                # Find matching row in Excel B
                match_rows_b = df_b_final[df_b_final["BC PO"].astype(str).str.contains(po)]
                if not match_rows_b.empty:
                    row_b = match_rows_b.iloc[0]
                    
                    differences = compare_rows(row_a, row_b, columns_to_compare)
                    if differences:
                        matched_differences.append({"PO": po, "Differences": differences})
            else:
                unmatched_pos.append(po)

        # Display results
        st.subheader("🔍 Matched PO Differences")
        if matched_differences:
            for item in matched_differences:
                st.markdown(f"<b>PO:</b> <code>{item['PO']}</code>", unsafe_allow_html=True)
                
                # Check what differences we have
                has_eta = "ETA" in item["Differences"]
                has_container = "Container" in item["Differences"]
                
                # Display according to rules
                if has_eta:
                    diff = item["Differences"]["ETA"]
                    st.markdown(
                        f"<span style='color:darkred'><b>ETA</b></span>: "
                        f"<span style='color:blue'><b>Excel A</b></span> = <span style='color:green'>'{diff['Excel A']}'</span>, "
                        f"<span style='color:blue'><b>Excel B</b></span> = <span style='color:orange'>'{diff['Excel B']}'</span>",
                        unsafe_allow_html=True
                    )
                
                if has_container:
                    diff = item["Differences"]["Container"]
                    st.markdown(
                        f"<span style='color:darkred'><b>Container</b></span>: "
                        f"<span style='color:blue'><b>Excel A</b></span> = <span style='color:green'>'{diff['Excel A']}'</span>, "
                        f"<span style='color:blue'><b>Excel B</b></span> = <span style='color:orange'>'{diff['Excel B']}'</span>",
                        unsafe_allow_html=True
                    )
                st.write("---")
        else:
            st.write("No differences found in matched POs.")

        st.subheader("❌ Unmatched PO Numbers from Excel A")
        if unmatched_pos:
            st.write(unmatched_pos)
        else:
            st.write("All PO numbers from Excel A matched with Excel B.")

        # Export buttons
        export_matched = []
        for item in matched_differences:
            row = {"PO": item["PO"]}
            for col, diff in item["Differences"].items():
                row[f"{col}_Excel_A"] = diff['Excel A']
                row[f"{col}_Excel_B"] = diff['Excel B']
            export_matched.append(row)

        if export_matched:
            st.download_button("📥 Download Matched Differences", data=convert_to_csv(export_matched),
                               file_name="matched_differences.csv", mime="text/csv")

        if unmatched_pos:
            st.download_button("📥 Download Unmatched PO Numbers", data=convert_to_csv(unmatched_pos, columns=["Unmatched PO"]),
                               file_name="unmatched_po.csv", mime="text/csv")
