import streamlit as st
import pandas as pd
import re
from io import BytesIO
import datetime
import openpyxl

st.set_page_config(page_title="DHL SHIPMENT CHECK LIST", layout="wide")
st.title("📦 DHL SHIPMENT CHECK LIST")

# --- FILE UPLOAD ---
file_a = st.file_uploader("Upload Excel A (ECLY_SHIPMENT_LEVEL_REPORT Report)", type=["xlsx", "csv"], key="file_a")
file_b = st.file_uploader("Upload Excel B (Import Doc)", type=["xlsx", "csv"], key="file_b")

# --- HELPER FUNCTIONS ---

def detect_header_row(df, keywords):
    """Detects the header row index based on the presence of specified keywords."""
    for i in range(min(20, len(df))):
        # Read the row, convert to string, strip whitespace, and check for keyword presence
        row = df.iloc[i].astype(str).str.strip().tolist()
        row_lower = [str(x).strip().lower() for x in row]
        keyword_lower = [k.strip().lower() for k in keywords]
        
        # Correct Check: Check if all keywords are present in any cell (case-insensitive)
        # This checks if (for all keywords k) (any cell in the row contains k).
        if all(any(k in cell for cell in row_lower) for k in keyword_lower):
            return i
    return None

def find_best_match(df_cols, target_name):
    """Finds the actual column name that matches the target name case-insensitively."""
    target_lower = target_name.lower().strip()
    for col in df_cols:
        if str(col).lower().strip() == target_lower:
            return col
    return None

def extract_po_numbers(order_value):
    """Extracts all 6-digit PO numbers, handling various formats."""
    if pd.isna(order_value):
        return []
    
    order_str = str(order_value).upper()
    
    # Clean the string to isolate 6-digit numbers from various prefixes/separators
    order_str = re.sub(r'[A-Z]+\s*#?\.?\s*', ' ', order_str) 
    order_str = re.sub(r'[/\-,]', ' ', order_str) 
    
    # Extract all contiguous 6-digit sequences
    return re.findall(r"\b\d{6}\b", order_str)

def normalize_eta(val):
    """Normalize ETA to date only (datetime.date object)"""
    if pd.isna(val) or val == "" or val is None:
        return None
    try:
        dt = pd.to_datetime(val)
        return dt.date()
    except:
        return None

def format_eta_display(eta_value):
    """Format ETA for display - date only without time"""
    if pd.isna(eta_value) or eta_value == "" or eta_value is None:
        return ""
    try:
        dt = pd.to_datetime(eta_value)
        return dt.strftime("%Y-%m-%d")
    except:
        return str(eta_value)

def normalize_vessel(vessel_value):
    """Normalize vessel names for comparison."""
    if pd.isna(vessel_value) or vessel_value == "" or vessel_value is None:
        return ""
        
    vessel_str = str(vessel_value).strip().upper()
    
    vessel_str = re.sub(r'[\s\-_]+', ' ', vessel_str)
    vessel_str = vessel_str.strip()
    vessel_str = re.sub(r'\bMV\s+', '', vessel_str)
    vessel_str = re.sub(r'\bV\.\s*', '', vessel_str)
    vessel_str = re.sub(r'\s+EXPRESS$', '', vessel_str)
    vessel_str = re.sub(r'\s+SERVICE$', '', vessel_str)
    vessel_str = re.sub(r'[/\-_]', ' ', vessel_str) # Replace internal separators with space
    vessel_str = vessel_str.replace(" ", "") # Remove all spaces for strict comparison
    
    # Standardize common vessel name variations
    vessel_replacements = {
        'CMACGM': 'CMACGM', 'MAERSKLINE': 'MAERSK', 'EVERGREENLINE': 'EVERGREEN',
        'COSCOSHIPPING': 'COSCO', 'HAPAGLLOYD': 'HAPAGLLOYD', 'ONELINE': 'ONE',
        'OOCLLIMITED': 'OOCL', 'YANGMING': 'YANGMING', 'KOTALEMBAH': 'KOTALEMBAH',
        'XINZHANGZHOU': 'XINZHANGZHOU'
    }
    
    for old, new in vessel_replacements.items():
        if old in vessel_str:
            return new
        
    return vessel_str

def normalize_voyage(voyage_value):
    """Normalize Arrival Voyage: extract number, remove leading 0 and trailing letters"""
    if pd.isna(voyage_value) or voyage_value == "" or voyage_value is None:
        return ""
        
    voyage_str = str(voyage_value).strip().upper()
    
    # Extract number sequence, possibly followed by letters (e.g., 540S, 2501, 133)
    voyage_match = re.search(r'(\d+[A-Z]*)', voyage_str)
    if voyage_match:
        voyage_num = voyage_match.group(1)
        return voyage_num.lstrip('0')
        
    return voyage_str

def normalize_container_type(container_type):
    """Normalize container types to handle variations"""
    if not container_type:
        return ""
        
    container_type = container_type.upper().strip()
    
    type_mappings = {
        "40RE": "40RE", "40REHC": "40RE", "40RH": "40RE",
        "40HC": "40HC", "40HCR": "40HC", "40HCRV": "40HC",
        "20GP": "20GP", "20RE": "20RE", "20RF": "20RF",
        "20FR": "20FR", "45HC": "45HC",
    }
    
    if container_type in type_mappings:
        return type_mappings[container_type]
        
    for base_type, normalized in type_mappings.items():
        if base_type in container_type:
            return normalized
            
    return container_type

def normalize_container_comparison(container_value):
    """Extracts container number and type for comparison."""
    if pd.isna(container_value) or container_value == "" or container_value is None:
        return {"number": "", "type": "", "display": ""}
        
    container_str = str(container_value).strip()
    
    # 1. Look for container number pattern (4 letters, 7 digits)
    container_num_match = re.search(r'([A-Za-z]{4}\d{7})', container_str)
    container_num = container_num_match.group(1).upper() if container_num_match else ""
    
    # 2. Look for container type (inside parenthesis or after number)
    type_match = re.search(r'[\(]?\s*([A-Za-z0-9]{2,})\s*[\)]?', container_str)
    container_type = type_match.group(1).upper() if type_match else ""

    # Refine type extraction if the matched type is actually the container number
    if container_type == container_num:
        container_type = ""
        
    normalized_type = normalize_container_type(container_type)

    if container_num:
        display_val = f"{container_num}({normalized_type})" if normalized_type else container_num
    elif normalized_type:
        display_val = f"({normalized_type})"
    else:
        display_val = container_str # Fallback to raw string

    return {
        "number": container_num,
        "type": normalized_type,
        "display": display_val
    }

def are_containers_equal(container_a_raw, container_b_raw):
    """Checks container equality based on specific rules."""
    norm_a = normalize_container_comparison(container_a_raw)
    norm_b = normalize_container_comparison(container_b_raw)

    num_a = norm_a["number"]
    num_b = norm_b["number"]
    type_a = norm_a["type"]
    type_b = norm_b["type"]
    
    # Rule 2: If both Excel A and Excel B have a number -> Equal (True - do not compare value)
    if num_a and num_b:
        return True

    # Rule 1: If Excel A has a number and Excel B does not (only type or empty) -> Difference (False)
    elif num_a and not num_b:
        return False 
    
    # Rule 3: No numbers found on EITHER side or only in B. Compare types.
    if type_a and type_b:
        if type_a == type_b:
            return True
        if type_a in type_b or type_b in type_a:
            return True
        return False 

    # If both container fields were completely empty
    if not num_a and not num_b and not type_a and not type_b and not str(container_a_raw).strip() and not str(container_b_raw).strip():
        return True
        
    return False

def compare_rows(row_a, row_b, columns_to_compare):
    """Compares rows and filters differences based on specific business rules."""
    differences = {}
    
    for col in columns_to_compare:
        val_a = row_a.get(col, "")
        val_b = row_b.get(col, "")

        if col == "ETA":
            date_a = normalize_eta(val_a)
            date_b = normalize_eta(val_b)
            if date_a != date_b:
                differences[col] = {
                    "Excel A": format_eta_display(val_a),
                    "Excel B": format_eta_display(val_b)
                }
                
        elif col == "Container":
            if not are_containers_equal(val_a, val_b):
                container_a_info = normalize_container_comparison(val_a)
                container_b_info = normalize_container_comparison(val_b)
                display_a = container_a_info["display"] if container_a_info["display"] else str(val_a)
                display_b = container_b_info["display"] if container_b_info["display"] else str(val_b)

                differences[col] = {
                    "Excel A": display_a,
                    "Excel B": display_b
                }
                
        elif col == "Arrival Vessel":
            norm_a = normalize_vessel(val_a)
            norm_b = normalize_vessel(val_b)
            
            if norm_a != norm_b:
                differences[col] = {
                    "Excel A": str(val_a),
                    "Excel B": str(val_b)
                }
                
        elif col == "Arrival Voyage":
            norm_a = normalize_voyage(val_a)
            norm_b = normalize_voyage(val_b)
            if norm_a != norm_b:
                differences[col] = {
                    "Excel A": str(val_a),
                    "Excel B": str(val_b)
                }
    
    # Apply comparison behavior rules
    has_eta_diff = "ETA" in differences
    has_container_diff = "Container" in differences
    has_vessel_diff = "Arrival Vessel" in differences
    has_voyage_diff = "Arrival Voyage" in differences
    
    filtered_differences = {}
    
    # ETA, Container, Arrival Vessel are core. Voyage is supplementary.
    is_core_diff = has_eta_diff or has_container_diff or has_vessel_diff

    if not is_core_diff and not has_voyage_diff:
        return {}
    
    if not is_core_diff and has_voyage_diff:
        # Rule: Arrival Voyage differences are only reported alongside one of the main three differences.
        return {}

    # If two or more core fields differ, include all differences (including Voyage if present)
    if sum([has_eta_diff, has_container_diff, has_vessel_diff]) >= 2:
        if has_eta_diff: filtered_differences["ETA"] = differences["ETA"]
        if has_container_diff: filtered_differences["Container"] = differences["Container"]
        if has_vessel_diff: filtered_differences["Arrival Vessel"] = differences["Arrival Vessel"]
        if has_voyage_diff: filtered_differences["Arrival Voyage"] = differences["Arrival Voyage"]
        
    # If exactly one core field differs, only show that core field difference (ignoring voyage)
    elif sum([has_eta_diff, has_container_diff, has_vessel_diff]) == 1:
        if has_eta_diff: filtered_differences = {"ETA": differences["ETA"]}
        elif has_container_diff: filtered_differences = {"Container": differences["Container"]}
        elif has_vessel_diff: filtered_differences = {"Arrival Vessel": differences["Arrival Vessel"]}
        
    return filtered_differences


def convert_to_csv(data, columns=None):
    """Converts a list of dicts or a list of items to a CSV byte object."""
    output = BytesIO()
    if isinstance(data, list) and all(isinstance(i, str) for i in data):
        df = pd.DataFrame(data, columns=["Unmatched PO"])
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(data, columns=columns)
        
    df.to_csv(output, index=False)
    return output.getvalue()

# --- MAIN LOGIC ---

if file_a and file_b:
    
    # --- STEP 1: Process Excel A (ECLY_SHIPMENT_LEVEL_REPORT) ---
    st.subheader("Processing Excel A (ECLY Report)")
    
    try:
        df_a_raw = pd.read_excel(file_a, sheet_name=0, header=None, engine="openpyxl")
    except Exception as e:
        st.error(f"Error reading Excel A: {e}")
        st.stop()
        
    # Detect header row (Corrected keywords: checking for 'Shipper Name' as seen in file)
    header_keywords = ["All References", "Shipper Name"] 
    header_row_index = detect_header_row(df_a_raw, header_keywords)

    if header_row_index is None:
        st.error("Could not detect header row in Excel A. Check for 'All References' and 'Shipper Name'.")
        st.stop()
    
    df_a = pd.read_excel(file_a, sheet_name=0, header=header_row_index, engine="openpyxl")
    st.success(f"Header for Excel A detected at row {header_row_index + 1}.")
    
    # Map required columns
    col_map_a = {
        'All References': 'PO_Raw', 'Estimated Arrival': 'ETA',
        'Vessel Name (Last Leg)': 'Arrival Vessel',
        'Voyage/Flight Number (Last Leg)': 'Arrival Voyage',
        'Container Number': 'Container_Number_A',
        'Container Type': 'Container_Type_A',
        'Shipper Name': 'Supplier',
    }
    
    rename_dict = {}
    for key_a, standard_name in col_map_a.items():
        actual_col_name = find_best_match(df_a.columns, key_a)
        if actual_col_name:
            rename_dict[actual_col_name] = standard_name
            
    df_a.rename(columns=rename_dict, inplace=True)
    
    required_a_standard = list(col_map_a.values())
    missing_a = [col for col in required_a_standard if col not in df_a.columns]
    
    if missing_a:
        st.error(f"Missing required columns in Excel A after mapping: {missing_a}")
        st.stop()
        
    # Filter and normalize Excel A
    df_a['ETA'] = pd.to_datetime(df_a['ETA'], errors='coerce')
    df_a_clean = df_a.dropna(subset=['ETA']).copy()
    
    today = datetime.date.today()
    three_days_ago = today - datetime.timedelta(days=3)
    df_a_clean = df_a_clean[df_a_clean["ETA"].dt.date >= three_days_ago].copy()
    
    df_a_clean["Container"] = df_a_clean["Container_Number_A"].fillna('').astype(str).str.strip() + \
                                '(' + df_a_clean["Container_Type_A"].fillna('').astype(str).str.strip() + ')'
    
    df_a_clean['PO_List'] = df_a_clean['PO_Raw'].apply(extract_po_numbers)
    df_a_clean = df_a_clean[df_a_clean['PO_List'].apply(lambda x: len(x) > 0)].copy()
    
    po_map_a = {}
    for idx, row in df_a_clean.iterrows():
        for po in row["PO_List"]:
            if po not in po_map_a:
                po_map_a[po] = row.to_dict()


    # --- STEP 2: Process Excel B (Import Doc) ---
    st.subheader("Processing Excel B (Import Doc)")

    try:
        xls_b = pd.ExcelFile(file_b)
        sheet_names_b = xls_b.sheet_names
        # --- USER REQUEST: Use the most right (last) sheet only ---
        target_sheet = sheet_names_b[-1]
    except Exception as e:
        st.error(f"Error reading Excel B: {e}")
        st.stop()
            
    st.info(f"Using the most right sheet (last sheet in the file): **{target_sheet}**")

    # Load with header=None to detect header
    df_b_raw = pd.read_excel(file_b, sheet_name=target_sheet, engine="openpyxl", header=None)
    header_keywords_b = ["BC PO", "ETA"] 
    header_row_index_b = detect_header_row(df_b_raw, header_keywords_b)
    
    if header_row_index_b is None:
         st.warning("Could not automatically detect header row in Excel B. Defaulting to first row.")
         header_row_index_b = 0
    else:
         st.success(f"Header for Excel B detected at row {header_row_index_b + 1}.")

    df_b = pd.read_excel(file_b, sheet_name=target_sheet, engine="openpyxl", header=header_row_index_b)
    
    # --- Column Mapping and Consolidation for Excel B (Robust to column name changes) ---
    df_b_final = pd.DataFrame()
    existing_columns = df_b.columns.tolist()
    mapped_columns = []
    
    # Keywords for mapping explicit columns (Designed to handle variations like 'ETA Dates' vs 'Estimated Arrival')
    mapping_keywords = {
        "BC PO": ['bc po', 'bcpo', 'lc', 'po/lc'],
        "ETA": ['estimated arrival', 'eta dates', 'eta'],
        "Arrival Vessel": ['vessel name', 'arrival vessel'],
        "Arrival Voyage": ['voyage', 'arrival voyage'],
        "Discharge Port": ['discharge port'], 
        "Freight Co": ['freight co'], 
        "Supplier": ['supplier'],
    }
    
    # 1. Map explicit columns first using flexible keyword search
    for standard_col, keywords in mapping_keywords.items():
        if standard_col not in df_b_final.columns:
            for col in existing_columns:
                col_lower = str(col).lower().strip().replace('/', ' ').replace('.', '').replace('#', '')
                if any(keyword in col_lower for keyword in keywords):
                    # Check for 'BC PO' to prefer the most dedicated column
                    if standard_col == "BC PO" and not ('bc po' in col_lower or 'po/lc' in col_lower):
                        continue
                        
                    df_b_final[standard_col] = df_b[col]
                    mapped_columns.append(f"'{col}' → '{standard_col}'")
                    break 

    # 2. Logistics Consolidation (For Vessel, Voyage)
    # If Arrival Vessel or Voyage are still missing, try to extract them from combined fields/fallbacks.
    if "Arrival Vessel" not in df_b_final.columns or "Arrival Voyage" not in df_b_final.columns:
        
        # Fallback 1: Use Vessel Name column if it exists and was not mapped already
        vessel_col = find_best_match(existing_columns, "Vessel Name")
        if "Arrival Vessel" not in df_b_final.columns and vessel_col and vessel_col not in df_b_final.columns:
            df_b_final["Arrival Vessel_Fallback"] = df_b[vessel_col].astype(str)
            
        # Fallback 2: Use Voyage column if it exists and was not mapped already
        voyage_col = find_best_match(existing_columns, "Voyage")
        if "Arrival Voyage" not in df_b_final.columns and voyage_col and voyage_col not in df_b_final.columns:
            df_b_final["Arrival Voyage_Fallback"] = df_b[voyage_col].astype(str)

    # 3. Container Consolidation 
    container_cols = []
    
    for col in existing_columns:
        col_lower = str(col).lower().strip().replace('/', ' ').replace('.', '').replace('#', '')
        if 'container' in col_lower or 'cont.' in col_lower:
             container_cols.append(col)
             
    if container_cols and "Container" not in df_b_final.columns:
        cols_to_concat = [c for c in container_cols if c in df_b.columns]
        
        df_b_final["Container"] = (
            df_b[cols_to_concat]
            .fillna('')
            .astype(str)
            .agg(lambda x: ', '.join(x[x.str.strip()!=''].values), axis=1) 
        )
        mapped_columns.append(f"'{', '.join(cols_to_concat)}' → 'Container (Consolidated)'")
    elif "Container" not in df_b_final.columns:
        df_b_final["Container"] = ""
        st.warning("Could not identify container columns in Excel B. Container comparison might be limited.")


    # --- Finalize Column Checks for Excel B ---
    
    # Prioritize explicitly mapped columns over fallbacks
    if "Arrival Vessel" not in df_b_final.columns and "Arrival Vessel_Fallback" in df_b_final.columns:
         df_b_final["Arrival Vessel"] = df_b_final["Arrival Vessel_Fallback"]
    if "Arrival Voyage" not in df_b_final.columns and "Arrival Voyage_Fallback" in df_b_final.columns:
         df_b_final["Arrival Voyage"] = df_b_final["Arrival Voyage_Fallback"]
         
    required_columns = ["BC PO", "ETA", "Container", "Arrival Vessel", "Arrival Voyage"]
    missing_columns = [col for col in required_columns if col not in df_b_final.columns]
        
    if missing_columns:
        st.error(f"Missing required columns in Excel B after mapping: {missing_columns}")
        st.stop()
        
    st.success("✅ Column Mapping Completed in Excel B (using robust heuristics).")
        
    # Extract PO numbers from Excel B
    po_set_b = set()
    for val in df_b_final["BC PO"]:
        po_set_b.update(extract_po_numbers(val))

    # --- STEP 3: Comparison Logic ---
    st.subheader("Comparison Results")
    
    matched_differences = []
    unmatched_pos = []

    columns_to_compare = ["ETA", "Container", "Arrival Vessel", "Arrival Voyage"]

    for po, row_a in po_map_a.items():
        if po in po_set_b:
            match_rows_b = df_b_final[
                df_b_final["BC PO"].astype(str).str.contains(po)
            ]
            
            if not match_rows_b.empty:
                row_b = match_rows_b.iloc[0].to_dict()
                differences = compare_rows(row_a, row_b, columns_to_compare)
                if differences:
                    matched_differences.append({"PO": po, "Differences": differences})
        else:
            unmatched_pos.append(po)

    # --- STEP 4: Display Results ---
    
    categorized_differences = {
        "Estimated Arrival": [], "Container": [], "Arrival Vessel": [], "Arrival Voyage": []
    }
    
    for item in matched_differences:
        po_number = item.get("PO")
        for col, diff in item.get("Differences", {}).items():
            display_category = col 
            if display_category == "ETA": display_category = "Estimated Arrival"
            
            if display_category in categorized_differences:
                diff_item = {
                    "PO Number": po_number,
                    "Excel A Value (ECLY)": diff.get('Excel A', 'N/A'),
                    "Excel B Value (Import Doc)": diff.get('Excel B', 'N/A')
                }
                categorized_differences[display_category].append(diff_item)
                
    st.subheader("🔍 Categorized PO Differences (ECLY Report $\leftrightarrow$ Import Doc)")
    
    display_order = ["Estimated Arrival", "Container", "Arrival Vessel", "Arrival Voyage"]
    found_differences = False
    
    for category in display_order:
        diff_list = categorized_differences[category]
        
        if diff_list:
            found_differences = True
            st.markdown(f"#### 🛑 Differences in {category}", unsafe_allow_html=True)
            df_diff = pd.DataFrame(diff_list)
            st.dataframe(df_diff, use_container_width=True, hide_index=True)
            st.markdown("---")
            
    if not found_differences:
        st.info("✅ No PO differences found across key fields in matched records.")
        
    st.subheader("❌ Unmatched PO Numbers from ECLY Report (Need to be added to Import Doc)")
    if unmatched_pos:
        st.write(pd.DataFrame(unmatched_pos, columns=["Unmatched PO Number"]))
    else:
        st.write("All required PO numbers from Excel A matched with Excel B.")

    # --- STEP 5: Export Buttons ---
    
    export_matched = []
    for item in matched_differences:
        row = {"PO": item["PO"]}
        for col, diff in item["Differences"].items():
            export_col_name = col if col != "ETA" else "Estimated Arrival"
            row[f"{export_col_name}_Excel_A"] = diff['Excel A']
            row[f"{export_col_name}_Excel_B"] = diff['Excel B']
        export_matched.append(row)

    col1, col2 = st.columns(2)
    
    if export_matched:
        with col1:
            st.download_button("📥 Download Matched Differences CSV", data=convert_to_csv(export_matched),
                                file_name="matched_differences.csv", mime="text/csv")

    if unmatched_pos:
        with col2:
            st.download_button("📥 Download Unmatched PO Numbers CSV", data=convert_to_csv(unmatched_pos, columns=["Unmatched PO"]),
                                file_name="unmatched_po.csv", mime="text/csv")
