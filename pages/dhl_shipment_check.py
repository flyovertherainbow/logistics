import streamlit as st
import pandas as pd
import re
from io import BytesIO
import datetime

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
        # Case-insensitive check for presence (allowing partial match for robustness)
        row_lower = [str(x).strip().lower() for x in row]
        keyword_lower = [k.strip().lower() for k in keywords]
        
        # Check if all keywords are present (case-insensitive)
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
    order_str = re.sub(r'[A-Z]+\s*#?\.?\s*', ' ', order_str) # Remove common PO, ORDER, NO prefixes
    order_str = re.sub(r'[/\-,]', ' ', order_str) # Replace internal separators with space
    
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
    
    # Remove extra spaces, hyphens, and common prefixes/suffixes
    vessel_str = re.sub(r'[\s\-_]+', ' ', vessel_str)
    vessel_str = vessel_str.strip()
    vessel_str = re.sub(r'\bMV\s+', '', vessel_str)
    vessel_str = re.sub(r'\bV\.\s*', '', vessel_str)
    vessel_str = re.sub(r'\s+EXPRESS$', '', vessel_str)
    vessel_str = re.sub(r'\s+SERVICE$', '', vessel_str)
    
    # Standardize common vessel name variations
    vessel_replacements = {
        'CMA CGM': 'CMACGM', 'MAERSK LINE': 'MAERSK', 'EVERGREEN LINE': 'EVERGREEN',
        'COSCO SHIPPING': 'COSCO', 'HAPAG LLOYD': 'HAPAG-LLOYD', 'ONE LINE': 'ONE',
        'OOCL LIMITED': 'OOCL', 'YANG MING': 'YANGMING',
    }
    
    for old, new in vessel_replacements.items():
        vessel_str = vessel_str.replace(old, new)
        
    return vessel_str

def normalize_voyage(voyage_value):
    """Normalize Arrival Voyage: remove leading 0 and trailing letters"""
    if pd.isna(voyage_value) or voyage_value == "" or voyage_value is None:
        return ""
        
    voyage_str = str(voyage_value).strip().upper()
    
    # Extract voyage number (usually digits, sometimes with letters)
    voyage_match = re.search(r'(\d+)[A-Z]*', voyage_str)
    if voyage_match:
        voyage_num = voyage_match.group(1)
        # Remove leading zeros
        return voyage_num.lstrip('0')
        
    return voyage_str

def normalize_container_type(container_type):
    """Normalize container types to handle variations"""
    if not container_type:
        return ""
        
    container_type = container_type.upper().strip()
    
    type_mappings = {
        "40RE": "40RE", "40REHC": "40RE", "40RH": "40RE", # Added 40RH for potential variations
        "40HC": "40HC", "40HCR": "40HC", "40HCRV": "40HC",
        "20GP": "20GP", "20RE": "20RE", "20RF": "20RF",
        "20FR": "20FR", "45HC": "45HC",
    }
    
    # Direct match or partial match
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
    
    # Pattern: [A-Za-z]{4}\d{7} followed by optional (type)
    # The pattern is: (Container Number) Optional_Text (Container Type)
    pattern = r'([A-Za-z]{4}\d{7})\s*[\(]?\s*([A-Za-z0-9]*)\s*[\)]?'
    match = re.search(pattern, container_str)
    
    if match:
        container_num = match.group(1).upper()
        container_type = match.group(2).upper()
        
        normalized_type = normalize_container_type(container_type)
        
        return {
            "number": container_num,
            "type": normalized_type,
            "display": f"{container_num}({normalized_type})" if normalized_type else container_num
        }
    else:
        # If no container number pattern found, try to extract just the type/raw value
        # This handles cases like: (20GP), or just a non-standard string
        type_pattern = r'[\(]?\s*([A-Za-z0-9]+)\s*[\)]?'
        type_match = re.search(type_pattern, container_str)
        if type_match and len(type_match.group(1)) >= 2:
            container_type = type_match.group(1).upper()
            normalized_type = normalize_container_type(container_type)
            if normalized_type:
                 return {
                    "number": "",
                    "type": normalized_type,
                    "display": f"({normalized_type})"
                }
            
    return {"number": "", "type": "", "display": container_str}

def are_containers_equal(container_a_raw, container_b_raw):
    """
    Checks container equality based on specific rules:
    1. If Excel A has a number and Excel B does not (only type or empty) -> Difference (False)
    2. If both Excel A and Excel B have a number -> Equal (True - do not compare value)
    3. If neither has a number -> Compare types (True if match/near match, False if different)
    """
    container_a_raw = str(container_a_raw)
    container_b_raw = str(container_b_raw)
    
    norm_a = normalize_container_comparison(container_a_raw)
    norm_b = normalize_container_comparison(container_b_raw)

    num_a = norm_a["number"]
    num_b = norm_b["number"]
    type_a = norm_a["type"]
    type_b = norm_b["type"]
    
    # 1. Check if both have numbers
    if num_a and num_b:
        # Rule: If container number exists in both, do not compare the value, treat as equal (True)
        return True

    # 2. Check for the specific rule: container number exists in A, but not in B (only type or empty)
    elif num_a and not num_b:
        # Rule: If Excel A has number and Excel B only has type/is empty -> Difference (False)
        return False 
    
    # 3. No numbers found on EITHER side or only in B (which is acceptable, as A is "source of truth")
    
    # Fallback to check if types match (e.g., '(20GP)' vs '(20GP)')
    if type_a and type_b:
        if type_a == type_b:
            return True
        # Allow original logic for near-matches (e.g., '20GP' in '20GPXX')
        if type_a in type_b or type_b in type_a:
            return True
        return False # Types are present but different

    # Final check: If both container fields were completely empty (no number and no type)
    if not container_a_raw.strip() and not container_b_raw.strip():
        return True
        
    # All other cases (e.g., one had a type/raw value, the other was empty) -> Difference
    # This covers the case where A is empty and B has a type, which should be flagged
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
                # Use the extracted info for display if available, otherwise raw value
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
        # If no differences at all
        return {}
    
    if not is_core_diff and has_voyage_diff:
        # Rule: Arrival Voyage differences are only reported alongside one of the main three differences.
        # This condition means we should ignore voyage-only differences.
        return {}

    # If only one core field differs, only that difference is shown.
    if is_core_diff and sum([has_eta_diff, has_container_diff, has_vessel_diff]) == 1:
        if has_eta_diff:
            filtered_differences = {"ETA": differences["ETA"]}
        elif has_container_diff:
            filtered_differences = {"Container": differences["Container"]}
        elif has_vessel_diff:
            filtered_differences = {"Arrival Vessel": differences["Arrival Vessel"]}
    
    # If two or more core fields differ, all fields showing a difference are reported.
    elif sum([has_eta_diff, has_container_diff, has_vessel_diff]) >= 2:
        # Include all core differences
        if has_eta_diff: filtered_differences["ETA"] = differences["ETA"]
        if has_container_diff: filtered_differences["Container"] = differences["Container"]
        if has_vessel_diff: filtered_differences["Arrival Vessel"] = differences["Arrival Vessel"]
        
        # Include voyage difference if it exists
        if has_voyage_diff:
             filtered_differences["Arrival Voyage"] = differences["Arrival Voyage"]
             
    # This block also captures the single core diff if voyage is present. 
    # Recalculating all differences for simplicity based on the rule that if there is a core diff,
    # and a voyage diff, report the voyage diff.
    if is_core_diff and has_voyage_diff:
        if "Arrival Voyage" in differences:
            filtered_differences["Arrival Voyage"] = differences["Arrival Voyage"]

    return filtered_differences


def convert_to_csv(data, columns=None):
    """Converts a list of dicts or a list of items to a CSV byte object."""
    output = BytesIO()
    if isinstance(data, list) and all(isinstance(i, str) for i in data):
        df = pd.DataFrame(data, columns=["Unmatched PO"])
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        # Fallback for unexpected data types
        df = pd.DataFrame(data, columns=columns)
        
    df.to_csv(output, index=False)
    return output.getvalue()

# --- MAIN LOGIC ---

if file_a and file_b:
    
    # --- STEP 1: Process Excel A (ECLY_SHIPMENT_LEVEL_REPORT) ---
    st.subheader("Processing Excel A (ECLY Report)")
    
    # Load raw data for header detection
    try:
        df_a_raw = pd.read_excel(file_a, sheet_name=0, header=None, engine="openpyxl")
    except Exception as e:
        st.error(f"Error reading Excel A: {e}")
        st.stop()
        
    # Detect header row (Corrected keywords: looking for 'Shipper Name' as seen in file)
    header_keywords = ["All References", "Shipper Name"]
    header_row_index = detect_header_row(df_a_raw, header_keywords)

    if header_row_index is None:
        st.error("Could not detect header row in Excel A. Check for 'All References' and 'Shipper Name'.")
        st.stop()
    
    # Load data with correct header
    df_a = pd.read_excel(file_a, sheet_name=0, header=header_row_index, engine="openpyxl")
    st.success(f"Header for Excel A detected at row {header_row_index + 1}.")
    
    # Map and rename required columns for comparison
    col_map_a = {
        'All References': 'PO_Raw', 
        'Estimated Arrival': 'ETA',
        'Vessel Name (Last Leg)': 'Arrival Vessel',
        'Voyage/Flight Number (Last Leg)': 'Arrival Voyage',
        'Container Number': 'Container_Number_A',
        'Container Type': 'Container_Type_A',
        'Shipper Name': 'Supplier', # FIX: Key is now 'Shipper Name' (from file), mapped to 'Supplier' (standard name)
    }
    
    # Create the actual renaming dictionary: {Actual Column Name: Standard Column Name}
    rename_dict = {}
    
    # Iterate through the expected keys (e.g., 'All References', 'Shipper Name')
    for key_a, standard_name in col_map_a.items():
        # Find the column in df_a that matches this expected key (case-insensitive)
        actual_col_name = find_best_match(df_a.columns, key_a)
        if actual_col_name:
            rename_dict[actual_col_name] = standard_name
            
    # Rename columns to standard names for processing
    df_a.rename(columns=rename_dict, inplace=True)
    
    # Check for missing required columns (now using the standardized names)
    required_a_standard = list(col_map_a.values())
    missing_a = [col for col in required_a_standard if col not in df_a.columns]
    
    if missing_a:
        st.error(f"Missing required columns in Excel A after mapping: {missing_a}")
        st.stop()
        
    # 1. Clean ETA and filter by date
    df_a['ETA'] = pd.to_datetime(df_a['ETA'], errors='coerce')
    df_a_clean = df_a.dropna(subset=['ETA']).copy()
    
    # Filter: ETA must be a validated date and from 3 days before current date.
    today = datetime.date.today()
    three_days_ago = today - datetime.timedelta(days=3)
    df_a_clean = df_a_clean[df_a_clean["ETA"].dt.date >= three_days_ago].copy()
    
    # 2. Add standardized 'Container' column (for comparison/display)
    # Excel A keeps number and type separate, combine them in the expected format: NUMBER(TYPE)
    df_a_clean["Container"] = df_a_clean["Container_Number_A"].fillna('').astype(str).str.strip() + \
                                '(' + df_a_clean["Container_Type_A"].fillna('').astype(str).str.strip() + ')'
    
    # 3. Extract PO numbers and filter rows
    df_a_clean['PO_List'] = df_a_clean['PO_Raw'].apply(extract_po_numbers)
    # Filter: rows that have validate PO Number at the columns All references.
    df_a_clean = df_a_clean[df_a_clean['PO_List'].apply(lambda x: len(x) > 0)].copy()
    
    # Final structure for comparison map
    po_map_a = {}
    for idx, row in df_a_clean.iterrows():
        for po in row["PO_List"]:
            # Store the final row data under each PO for lookup
            # Use po_map_a.get(po, {}) to handle multiple POs per row, ensuring we keep all data
            if po not in po_map_a:
                po_map_a[po] = row.to_dict()
            # If multiple rows have the same PO, this logic uses the first row found (which is acceptable for comparison)


    # --- STEP 2: Process Excel B (Import Doc) ---
    st.subheader("Processing Excel B (Import Doc)")

    # Load Excel B with logic to select the most recent sheet based on MM.YYYY format
    try:
        xls_b = pd.ExcelFile(file_b)
        sheet_names_b = xls_b.sheet_names
    except Exception as e:
        st.error(f"Error reading Excel B: {e}")
        st.stop()
    
    latest_date = None
    latest_sheet = None

    for sheet in sheet_names_b:
        try:
            # Check for MM.YYYY format
            date_obj = datetime.datetime.strptime(sheet.strip(), "%m.%Y")
            if latest_date is None or date_obj > latest_date:
                latest_date = date_obj
                latest_sheet = sheet
        except ValueError:
            continue

    if latest_sheet:
        # Load initially with header=None to detect header
        df_b = pd.read_excel(file_b, sheet_name=latest_sheet, engine="openpyxl", header=None)
        st.info(f"Using the most recent sheet: **{latest_sheet}**")
    else:
        last_sheet = sheet_names_b[-1]
        df_b = pd.read_excel(file_b, sheet_name=last_sheet, engine="openpyxl", header=None)
        st.info(f"Using the last sheet: **{last_sheet}**")

    # Detect header row in Excel B
    header_keywords_b = ["BC PO", "ETA"] 
    header_row_index_b = detect_header_row(df_b, header_keywords_b)
    
    if header_row_index_b is None:
         st.warning("Could not automatically detect header row in Excel B. Defaulting to first non-empty row (index 0).")
         header_row_index_b = 0
         # Reload using the raw data from df_b_raw but setting the header manually if needed
         # Since df_b is already header=None, we can proceed and map the columns by position/heuristic
    else:
         st.success(f"Header for Excel B detected at row {header_row_index_b + 1}.")
         # Reload the data with the correct header row
         df_b = pd.read_excel(file_b, sheet_name=latest_sheet if latest_sheet else last_sheet, engine="openpyxl", header=header_row_index_b)
    
    # --- Column Mapping and Consolidation for Excel B ---
    
    df_b_final = pd.DataFrame()
    existing_columns = df_b.columns.tolist()
    mapped_columns = []
    
    # Define keywords for mapping
    # Note: Using case-insensitive partial matching for robust column identification
    mapping_keywords = {
        "BC PO": ['bc po', 'bcpo', 'lc', 'po/lc'],
        "ETA": ['estimated arrival', 'eta dates', 'eta'],
        "Arrival Vessel": ['vessel name', 'arrival vessel'],
        "Arrival Voyage": ['voyage/flight number', 'arrival voyage', 'voyage'],
        "Supplier": ['supplier'],
    }
    
    # Map scalar columns
    for standard_col, keywords in mapping_keywords.items():
        if standard_col not in df_b_final.columns:
            for col in existing_columns:
                col_lower = str(col).lower().strip().replace('/', ' ').replace('.', '').replace('#', '')
                if any(keyword in col_lower for keyword in keywords):
                    # Heuristic to avoid mapping 'Arrival Vessel' to a generic 'Freight Co' if a better match exists.
                    if standard_col == "Arrival Vessel" and any(k in col_lower for k in ['freight co', 'freight']):
                        continue
                        
                    df_b_final[standard_col] = df_b[col]
                    mapped_columns.append(f"'{col}' → '{standard_col}'")
                    break # Move to next standard column once found

    # Map Container columns (Consolidation)
    container_cols = []
    
    for col in existing_columns:
        col_lower = str(col).lower().strip().replace('/', ' ').replace('.', '').replace('#', '')
        # Check for columns explicitly named 'Container' or starting with 'Container NO.'
        if 'container' in col_lower or 'cont.' in col_lower:
             container_cols.append(col)
             
    # Try to find adjacent container columns for consolidation
    if not container_cols:
        # Heuristic: Find first column that looks like container NO. and take next few
        for col_name in existing_columns:
            if str(col_name).strip().upper().startswith('CONTAINER NO'):
                start_index = existing_columns.index(col_name)
                # Take the column and next 5 adjacent columns for consolidation
                container_cols = existing_columns[start_index:start_index + 6]
                break
            
    if container_cols:
        cols_to_concat = [c for c in container_cols if c in df_b.columns]
        
        # Concatenate non-empty values from these columns into a single, standardized Container column, separated by a comma.
        df_b_final["Container"] = (
            df_b[cols_to_concat]
            .fillna('')
            .astype(str)
            .agg(lambda x: ', '.join(x[x.str.strip()!=''].values), axis=1) 
        )
        mapped_columns.append(f"'{', '.join(cols_to_concat)}' → 'Container (Consolidated)'")
    else:
        df_b_final["Container"] = ""
        st.warning("Could not identify container columns in Excel B. Container comparison might be limited.")

    st.success("✅ Column Mapping Completed in Excel B:")
    for mapping in mapped_columns:
        st.write(f" - {mapping}")
    
    required_columns = ["BC PO", "ETA", "Container", "Arrival Vessel", "Arrival Voyage"]
    missing_columns = [col for col in required_columns if col not in df_b_final.columns]
        
    if missing_columns:
        st.error(f"Missing required columns in Excel B after mapping: {missing_columns}")
        st.stop()
        
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
            # Find matching row in Excel B
            # Find a row where the 'BC PO' column contains the PO number string
            match_rows_b = df_b_final[
                df_b_final["BC PO"].astype(str).str.contains(po)
            ]
            
            if not match_rows_b.empty:
                # Use the first match
                row_b = match_rows_b.iloc[0].to_dict()
                
                # Perform comparison
                differences = compare_rows(row_a, row_b, columns_to_compare)
                if differences:
                    matched_differences.append({"PO": po, "Differences": differences})
        else:
            unmatched_pos.append(po)

    # --- STEP 4: Display Results ---
    
    TARGET_CATEGORIES = {
        "ETA": "Estimated Arrival",
        "CONTAINER": "Container",
        "ARRIVAL VESSEL": "Arrival Vessel",
        "ARRIVAL VOYAGE": "Arrival Voyage"
    }
    categorized_differences = {v: [] for v in TARGET_CATEGORIES.values()}
    
    for item in matched_differences:
        po_number = item.get("PO")
        if not po_number:
            continue
            
        for col, diff in item.get("Differences", {}).items():
            display_category = col 
            
            if display_category in categorized_differences:
                diff_item = {
                    "PO Number": po_number,
                    "Excel A Value": diff.get('Excel A', 'N/A'),
                    "Excel B Value": diff.get('Excel B', 'N/A')
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
            
            # Convert list of dicts to DataFrame for clean display
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
    # Re-structure for clean export
    for item in matched_differences:
        row = {"PO": item["PO"]}
        for col, diff in item["Differences"].items():
            row[f"{col}_Excel_A"] = diff['Excel A']
            row[f"{col}_Excel_B"] = diff['Excel B']
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
