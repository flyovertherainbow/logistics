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

# Improved container comparison logic
def normalize_container_comparison(container_value):
    if pd.isna(container_value) or container_value == "" or container_value is None:
        return {"number": "", "type": "", "display": ""}
    
    container_str = str(container_value).strip()
    
    # Extract container number and type
    # Pattern for 4 letters + 7 digits followed by container type
    pattern = r'([A-Za-z]{4}\d{7})\s*[\(]?\s*([A-Za-z0-9]*)\s*[\)]?'
    match = re.search(pattern, container_str)
    
    if match:
        container_num = match.group(1).upper()
        container_type = match.group(2).upper()
        
        # Handle container type variations
        normalized_type = normalize_container_type(container_type)
        
        return {
            "number": container_num, 
            "type": normalized_type,
            "display": f"{container_num}({normalized_type})" if normalized_type else container_num
        }
    else:
        # If no container number pattern found, try to extract just the type
        type_pattern = r'[\(]?\s*([A-Za-z0-9]+)\s*[\)]?'
        type_match = re.search(type_pattern, container_str)
        if type_match and len(type_match.group(1)) >= 2:
            container_type = type_match.group(1).upper()
            normalized_type = normalize_container_type(container_type)
            return {
                "number": "", 
                "type": normalized_type,
                "display": f"({normalized_type})" if normalized_type else container_str
            }
    
    return {"number": "", "type": "", "display": container_str}

def normalize_container_type(container_type):
    """Normalize container types to handle variations"""
    if not container_type:
        return ""
    
    container_type = container_type.upper().strip()
    
    # Handle common container type variations
    type_mappings = {
        # If one type includes another, treat them as same
        "40RE": "40RE",      # Base type
        "40REHC": "40RE",    # 40REHC includes 40RE, so treat as same
        "40HC": "40HC",
        "40HCR": "40HC",     # 40HCR includes 40HC, so treat as same
        "40HCRV": "40HC",    # 40HCRV includes 40HC, so treat as same
        "20GP": "20GP",
        "20RE": "20RE",
        "20RF": "20RF",
        "20FR": "20FR",
        "45HC": "45HC",
    }
    
    # Check for exact match first
    if container_type in type_mappings:
        return type_mappings[container_type]
    
    # Check if any base type is included in the current type
    for base_type, normalized in type_mappings.items():
        if base_type in container_type:
            return normalized
    
    # If no mapping found, return the original type
    return container_type

def are_containers_equal(container_a, container_b):
    """Check if two containers are considered equal after normalization"""
    norm_a = normalize_container_comparison(container_a)
    norm_b = normalize_container_comparison(container_b)
    
    # Compare container numbers (if both have them)
    if norm_a["number"] and norm_b["number"]:
        if norm_a["number"] != norm_b["number"]:
            return False
    
    # Compare container types with inclusion logic
    if norm_a["type"] and norm_b["type"]:
        # If types are exactly the same
        if norm_a["type"] == norm_b["type"]:
            return True
        # If one type includes the other, treat as same
        if norm_a["type"] in norm_b["type"] or norm_b["type"] in norm_a["type"]:
            return True
        return False
    
    # If one has no type, compare what we have
    return norm_a["display"] == norm_b["display"]

# Get display value for any column
def get_display_value(value, col_name):
    if pd.isna(value) or value == "" or value is None:
        return ""
    
    if col_name == "ETA":
        return format_eta_display(value)
    elif col_name == "Container":
        container_info = normalize_container_comparison(value)
        return container_info["display"]
    else:
        return str(value)

# Updated compare_rows function with improved container comparison
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
            # Use the improved container comparison logic
            if not are_containers_equal(val_a, val_b):
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

    # Show original Excel B columns
    existing_columns = df_b.columns.tolist()
    st.write("📋 Original Excel B Columns:", existing_columns)

    # Create a new DataFrame with properly mapped columns (avoid duplicates)
    df_b_final = pd.DataFrame()
    mapped_columns = []
    
    # Map each column individually to avoid duplicates
    for col in existing_columns:
        col_lower = str(col).lower().strip()
        
        if 'bc po' in col_lower or 'bcpo' in col_lower or ('po' in col_lower and 'bc' in col_lower):
            if "BC PO" not in df_b_final.columns:
                df_b_final["BC PO"] = df_b[col]
                mapped_columns.append(f"'{col}' → 'BC PO'")
        elif 'estimated arrival' in col_lower or 'eta' in col_lower:
            if "ETA" not in df_b_final.columns:
                df_b_final["ETA"] = df_b[col]
                mapped_columns.append(f"'{col}' → 'ETA'")
        elif 'container' in col_lower:
            if "Container" not in df_b_final.columns:
                df_b_final["Container"] = df_b[col]
                mapped_columns.append(f"'{col}' → 'Container'")
        elif 'arrival vessel' in col_lower or ('vessel' in col_lower and 'arrival' in col_lower):
            if "Arrival Vessel" not in df_b_final.columns:
                df_b_final["Arrival Vessel"] = df_b[col]
                mapped_columns.append(f"'{col}' → 'Arrival Vessel'")
        elif 'arrival voyage' in col_lower or ('voyage' in col_lower and 'arrival' in col_lower):
            if "Arrival Voyage" not in df_b_final.columns:
                df_b_final["Arrival Voyage"] = df_b[col]
                mapped_columns.append(f"'{col}' → 'Arrival Voyage'")
        elif 'supplier' in col_lower:
            if "Supplier" not in df_b_final.columns:
                df_b_final["Supplier"] = df_b[col]
                mapped_columns.append(f"'{col}' → 'Supplier'")

    st.success("✅ Column Mapping Completed:")
    for mapping in mapped_columns:
        st.write(f"   - {mapping}")

    # Check if we have the required columns
    required_columns = ["BC PO", "ETA", "Container"]
    missing_columns = [col for col in required_columns if col not in df_b_final.columns]
    
    if missing_columns:
        st.error(f"Missing required columns in Excel B: {missing_columns}")
        st.stop()

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
        for val in df_b_final["BC PO"]:
            po_set_b.update(extract_po_numbers(val))

        matched_differences = []
        unmatched_pos = []

        columns_to_compare = ["ETA", "Container"]

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
