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

# Enhanced Arrival Vessel Normalization
def normalize_vessel(vessel_value):
    """
    Normalize vessel names for comparison:
    - Convert to uppercase
    - Remove extra spaces and special characters
    - Standardize common vessel name variations
    """
    if pd.isna(vessel_value) or vessel_value == "" or vessel_value is None:
        return ""
    
    vessel_str = str(vessel_value).strip()
    
    # Convert to uppercase for consistent comparison
    vessel_str = vessel_str.upper()
    
    # Remove extra spaces, hyphens, and special characters
    vessel_str = re.sub(r'[\s\-_]+', ' ', vessel_str)
    vessel_str = vessel_str.strip()
    
    # Standardize common vessel prefixes/suffixes
    vessel_str = re.sub(r'\bMV\s+', '', vessel_str)  # Remove MV prefix
    vessel_str = re.sub(r'\bV\.\s*', '', vessel_str)  # Remove V. prefix
    vessel_str = re.sub(r'\s+EXPRESS$', '', vessel_str)  # Remove EXPRESS suffix
    vessel_str = re.sub(r'\s+SERVICE$', '', vessel_str)  # Remove SERVICE suffix
    
    # Handle common vessel name variations
    vessel_replacements = {
        'CMA CGM': 'CMACGM',
        'MAERSK LINE': 'MAERSK',
        'EVERGREEN LINE': 'EVERGREEN',
        'COSCO SHIPPING': 'COSCO',
        'HAPAG LLOYD': 'HAPAG-LLOYD',
        'ONE LINE': 'ONE',
        'OOCL LIMITED': 'OOCL',
        'YANG MING': 'YANGMING',
    }
    
    for old, new in vessel_replacements.items():
        vessel_str = vessel_str.replace(old, new)
    
    return vessel_str

# Normalize Arrival Voyage: remove leading 0 and trailing letters
def normalize_voyage(voyage_value):
    if pd.isna(voyage_value) or voyage_value == "" or voyage_value is None:
        return ""
    
    voyage_str = str(voyage_value).strip().upper()
    
    # Extract voyage number (usually digits, sometimes with letters)
    # Pattern: digits optionally followed by letters (e.g., "123E", "456W")
    voyage_match = re.search(r'(\d+)[A-Z]*', voyage_str)
    if voyage_match:
        voyage_num = voyage_match.group(1)
        # Remove leading zeros
        return voyage_num.lstrip('0')
    
    return voyage_str

# Enhanced Container Comparison Logic
def normalize_container_comparison(container_value):
    if pd.isna(container_value) or container_value == "" or container_value is None:
        return {"number": "", "type": "", "display": ""}
    
    container_str = str(container_value).strip()
    
    # Extract container number and type
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
        "40RE": "40RE",
        "40REHC": "40RE",
        "40HC": "40HC",
        "40HCR": "40HC",
        "40HCRV": "40HC",
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
    
    return container_type

def are_containers_equal(container_a, container_b):
    """
    Checks container equality based on the user's specific business logic:
    1. If one has a full 11-digit number and the other does not, they are DIFFERENT.
    2. If BOTH have a full 11-digit number, they are considered the SAME.
    3. If NEITHER has a number, comparison falls back to container type.
    """
    # NOTE: The helper function normalize_container_comparison must be called first
    # to reliably extract the 'number' and 'type' components.
    
    norm_a = normalize_container_comparison(container_a)
    norm_b = normalize_container_comparison(container_b)

    num_a = norm_a["number"]
    num_b = norm_b["number"]
    type_a = norm_a["type"]
    type_b = norm_b["type"]

    # --- 1. & 2. Number Presence Check (User's Custom Logic) ---

    # Rule: Both have a number (4 letters + 7 digits)
    if num_a and num_b:
        # User requirement: "both side have container number then do not do comparation."
        # This means they are considered equal for the purpose of difference reporting.
        return True

    # Rule: Only one side has a container number
    # (A has number AND B does NOT) OR (A does NOT have number AND B has number)
    if (num_a and not num_b) or (not num_a and num_b):
        # They are different because one has the specific number and the other is missing it.
        return False

    # --- 3. No numbers found on EITHER side (Both empty/type only) ---

    # Rule: Check if the container types (e.g., "20GP") are the same.
    if type_a and type_b:
        if type_a == type_b:
            return True
        # Keep original logic for near-matches (e.g., '40HC' vs '40HCR')
        if type_a in type_b or type_b in type_a:
             return True
        
        # Types are present but different
        return False

    # Rule: Check if one has a type and the other is empty (e.g., A="20GP", B="")
    if (type_a and not type_b) or (not type_a and type_b):
        return False
        
    # Rule: Both are completely empty. Treat as SAME.
    return True

# Enhanced Comparison Function with Vessel Comparison
def compare_rows(row_a, row_b, columns_to_compare):
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
                differences[col] = {
                    "Excel A": container_a_info["display"],
                    "Excel B": container_b_info["display"]
                }
                
        elif col == "Arrival Vessel":
            norm_a = normalize_vessel(val_a)
            norm_b = normalize_vessel(val_b)
            
            # Check if vessels are different after normalization
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
    
    # Enhanced filtering logic including vessel comparison
    filtered_differences = {}
    
    if has_eta_diff and not has_container_diff and not has_vessel_diff:
        # Only ETA differences → show only ETA
        filtered_differences = {"ETA": differences["ETA"]}
    elif has_container_diff and not has_eta_diff and not has_vessel_diff:
        # Only Container differences → show only Container
        filtered_differences = {"Container": differences["Container"]}
    elif has_vessel_diff and not has_eta_diff and not has_container_diff:
        # Only Vessel differences → show only Vessel
        filtered_differences = {"Arrival Vessel": differences["Arrival Vessel"]}
    elif has_eta_diff and has_container_diff:
        # Both ETA and Container differ → show both
        filtered_differences = {
            "ETA": differences["ETA"],
            "Container": differences["Container"]
        }
    elif has_eta_diff and has_vessel_diff:
        # ETA and Vessel differ → show both
        filtered_differences = {
            "ETA": differences["ETA"],
            "Arrival Vessel": differences["Arrival Vessel"]
        }
    elif has_container_diff and has_vessel_diff:
        # Container and Vessel differ → show both
        filtered_differences = {
            "Container": differences["Container"],
            "Arrival Vessel": differences["Arrival Vessel"]
        }
    elif has_eta_diff and has_container_diff and has_vessel_diff:
        # All three differ → show all
        filtered_differences = {
            "ETA": differences["ETA"],
            "Container": differences["Container"],
            "Arrival Vessel": differences["Arrival Vessel"]
        }
    
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
    required_columns = ["BC PO", "ETA", "Container", "Arrival Vessel"]
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

        # Show sample data from both files
        st.subheader("📊 Sample Data Preview")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("Excel A Sample (3 rows):")
            display_cols_a = ["Order #", "ETA"]
            if "Container" in df_a_clean.columns:
                display_cols_a.append("Container")
            if "Arrival Vessel" in df_a_clean.columns:
                display_cols_a.append("Arrival Vessel")
            sample_a = df_a_clean[display_cols_a].head(3).copy()
            sample_a["ETA"] = sample_a["ETA"].apply(format_eta_display)
            st.dataframe(sample_a)
        
        with col2:
            st.write("Excel B Sample (3 rows):")
            display_cols_b = ["BC PO", "ETA", "Container"]
            if "Arrival Vessel" in df_b_final.columns:
                display_cols_b.append("Arrival Vessel")
            sample_b = df_b_final[display_cols_b].head(3).copy()
            sample_b["ETA"] = sample_b["ETA"].apply(format_eta_display)
            st.dataframe(sample_b)

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
        # --- START REVISED CATEGORIZATION LOGIC (Fix for Key Mismatch) ---

        # Define the target categories for case-insensitive and space-insensitive matching
        # Maps the standardized (UPPERCASE) key to the official display name
        TARGET_CATEGORIES = {
            "ETA": "ETA",
            "CONTAINER": "Container",
            "ARRIVAL VESSEL": "Arrival Vessel",
            "ARRIVAL VOYAGE": "Arrival Voyage"
        }
        # Initialize the final structure using the official display names
        categorized_differences = {v: [] for v in TARGET_CATEGORIES.values()}
        
        # 1. Loop through all POs that had differences
        for item in matched_differences:
            # Use .get() for safe access
            po_number = item.get("PO Number") 
            
            if not po_number:
                continue
        
            # 2. Loop through the differences found for that PO
            for col, diff in item.get("Differences", {}).items():
                
                # Standardize the key from the Differences dictionary (e.g., "Container " -> "CONTAINER")
                standardized_key = str(col).strip().upper()
        
                # Check if this standardized key is one of our targets
                if standardized_key in TARGET_CATEGORIES:
                    
                    # Get the official display name (e.g., "Container" not "CONTAINER")
                    display_category = TARGET_CATEGORIES[standardized_key]
                    
                    # Create a clean item for display
                    diff_item = {
                        "PO Number": po_number,
                        # Use .get() for safe access to inner difference values
                        "Excel A Value": diff.get('Excel A', 'N/A'),
                        "Excel B Value": diff.get('Excel B', 'N/A')
                    }
                    # Append to the correct category list
                    categorized_differences[display_category].append(diff_item)
        
        # --- END REVISED CATEGORIZATION LOGIC ---
        # --- START NEW DISPLAY LOGIC ---

        st.subheader("🔍 Categorized PO Differences")
        
        # Define the logical display order
        display_order = ["ETA", "Container", "Arrival Vessel", "Arrival Voyage"]
        found_differences = False
        
        for category in display_order:
            diff_list = categorized_differences[category]
            
            if diff_list:
                found_differences = True
                
                # Use HTML for a strong, visible category header
                st.markdown(f"#### 🛑 Differences in {category}", unsafe_allow_html=True)
                
                for diff_item in diff_list:
                    po = diff_item["PO Number"]
                    val_a = diff_item["Excel A Value"]
                    val_b = diff_item["Excel B Value"]
                    
                    # Format the output for a single difference (using your styled HTML)
                    st.markdown(
                        f"**PO {po}**: "
                        f"<span style='color:blue'><b>Excel A</b></span> = <span style='color:green'>'{val_a}'</span>, "
                        f"<span style='color:blue'><b>Excel B</b></span> = <span style='color:orange'>'{val_b}'</span>",
                        unsafe_allow_html=True
                    )
                
                # Add a clear separator between categories
                st.markdown("---")
        
        if not found_differences:
            st.info("✅ No PO differences found across ETA, Container, Arrival Vessel, or Arrival Voyage in matched records.")
        
        # --- END NEW DISPLAY LOGIC ---
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

