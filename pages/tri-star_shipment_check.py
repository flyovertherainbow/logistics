import streamlit as st
import pandas as pd
import re
from io import BytesIO
from datetime import datetime
from functools import reduce

# --- Helper Functions ---

def read_excel_sheets(uploaded_file, original_name):
    """
    Reads all sheets from an Excel file (or mock CSVs for Sheets) into a dictionary of DataFrames.
    If the file is a single CSV, it returns it as a single 'Sheet 1'.
    """
    try:
        # Check if the uploaded object is a list of "Sheet" CSVs (common in this environment)
        # We look for files where the original Excel name is a prefix of the uploaded filename.
        if isinstance(uploaded_file, list):
             # Filter based on original name to avoid mixing files
             # Note: In a true Streamlit deployment, st.file_uploader returns a single object.
             # This setup handles the environment's specific way of mock-splitting Excel files.
            
            sheet_dfs = {}
            for f in uploaded_file:
                # Extract sheet name from filename format: "OriginalName.xlsx - Sheet Name.csv"
                try:
                    sheet_name_match = re.search(r' - (.*)\.csv$', f.name)
                    sheet_name = sheet_name_match.group(1) if sheet_name_match else f.name
                    f.seek(0)
                    df = pd.read_csv(f)
                    sheet_dfs[sheet_name] = df
                except Exception as e:
                    st.warning(f"Could not process sheet {f.name}: {e}")
            return sheet_dfs
        
        # If it's a single file object, treat it as a single sheet or an actual Excel file
        uploaded_file.seek(0)
        return {"Sheet 1": pd.read_excel(uploaded_file, sheet_name=None)}
        
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

def detect_header_row(df, keywords_a):
    """Detects the header row index by searching for keywords in the first 20 rows."""
    max_rows = min(len(df), 20)
    for i in range(max_rows):
        row = df.iloc[i].astype(str).str.lower().str.strip()
        if all(any(key.lower() in col for col in row.values) for key in keywords_a):
            return i
    return 0 # Fallback to 0 if not found

def get_latest_import_sheet(sheet_dfs):
    """Selects the sheet with the latest MM.YYYY date, or the last sheet as fallback."""
    date_sheets = {}
    for name, df in sheet_dfs.items():
        # Regex for MM.YYYY date format
        match = re.search(r'(\d{1,2}\.\d{4})', name)
        if match:
            try:
                # Parse as month and year
                date_obj = datetime.strptime(match.group(1), '%m.%Y')
                date_sheets[name] = date_obj
            except ValueError:
                continue

    if date_sheets:
        latest_sheet_name = max(date_sheets, key=date_sheets.get)
        return sheet_dfs[latest_sheet_name], latest_sheet_name
    
    # Fallback: get the last sheet if no date is found
    if sheet_dfs:
        last_sheet_name = list(sheet_dfs.keys())[-1]
        return sheet_dfs[last_sheet_name], last_sheet_name
        
    return None, None

def normalize_po(po_str):
    """Extracts all contiguous 6-digit numbers, handling separators like '/' and prefixes."""
    if pd.isna(po_str) or po_str == '':
        return []
    
    po_str = str(po_str).upper()
    
    # Remove PO/PO./PO# prefixes
    po_str = re.sub(r'P\.?O\#?', '', po_str)
    
    # Replace non-digit/non-separator characters with space, keep '/'
    po_str = re.sub(r'[^\d\/\.\-\s]', ' ', po_str)
    
    # Split by common separators (/, ., -) and whitespace
    parts = re.split(r'[\/\.\-\s]+', po_str)
    
    extracted_pos = []
    for part in parts:
        # Find 6-digit numbers in each part
        matches = re.findall(r'\b(\d{6})\b', part)
        extracted_pos.extend(matches)
            
    # Remove duplicates and return
    return sorted(list(set(extracted_pos)))

def extract_container_info(container_str):
    """
    Extracts the container number (4 letters + 7 digits) and type (e.g., (20GP)).
    Returns (number, type).
    """
    if pd.isna(container_str) or container_str == '':
        return None, None
    
    container_str = str(container_str).upper().strip()
    
    # Regex for container number (4 letters + 7 digits)
    num_match = re.search(r'([A-Z]{4}\d{7})', container_str)
    number = num_match.group(1) if num_match else None
    
    # Regex for container type (e.g., (20GP))
    type_match = re.search(r'(\([A-Z0-9]+\))', container_str)
    type_str = type_match.group(1) if type_match else None
    
    return number, type_str

def get_col_name(df, keywords):
    """Finds the first column name that contains any of the keywords."""
    for col in df.columns:
        if any(key.lower() in str(col).lower() for key in keywords):
            return col
    return None

def normalize_vessel(vessel_str):
    """Strips spaces and converts to uppercase for comparison."""
    if pd.isna(vessel_str):
        return None
    return str(vessel_str).replace(' ', '').upper().strip()


# --- Processing Logic ---

def process_import_doc(sheet_dfs):
    """Processes Excel B (Import Doc) to select the latest sheet and standardize columns."""
    
    df_b, sheet_name = get_latest_import_sheet(sheet_dfs)
    if df_b is None:
        st.error("No valid sheets found in Import Doc file.")
        return None

    st.info(f"Using sheet: **{sheet_name}** from Import Doc.")

    # 1. Column Mapping (Keywords for Flexible Column Names)
    col_map = {
        'po_col': get_col_name(df_b, ['po', 'bc po', 'lc']),
        'eta_col': get_col_name(df_b, ['eta dates', 'estimated arrival', 'eta']),
        'vessel_col': get_col_name(df_b, ['arrival vessel', 'vessel name', 'vessel']),
        'voyage_col': get_col_name(df_b, ['arrival voyage', 'voyage']),
    }
    
    # Filter out missing columns
    df_b_proc = pd.DataFrame()
    for new_name, old_col in [('BC PO', col_map['po_col']), 
                              ('ETA', col_map['eta_col']), 
                              ('Arrival Vessel', col_map['vessel_col']),
                              ('Arrival Voyage', col_map['voyage_col'])]:
        if old_col:
            df_b_proc[new_name] = df_b[old_col]
        else:
            df_b_proc[new_name] = pd.NA
            st.warning(f"Could not find a column for **{new_name}** in Import Doc. (Keywords: {new_name.lower().split()})")


    # 2. Container Consolidation
    container_cols = [col for col in df_b.columns if 'container' in str(col).lower()]
    
    # Take up to the first 6 container columns
    container_cols = container_cols[:6]

    if container_cols:
        # Function to combine container values, ignoring NaNs
        def combine_containers(row):
            return ', '.join(str(val) for val in row if pd.notna(val) and str(val).strip() != '')

        df_b_proc['Container'] = df_b[container_cols].apply(combine_containers, axis=1)
    else:
        df_b_proc['Container'] = pd.NA
        st.warning("Could not find any 'container' columns for consolidation in Import Doc.")
        
    # 3. PO Extraction and Explosion (One row per PO)
    exploded_list = []
    for index, row in df_b_proc.iterrows():
        po_numbers = normalize_po(row['BC PO'])
        if not po_numbers:
            # Keep original row for unmatched tracking, but set PO to NaN
            new_row = row.copy()
            new_row['PO_Clean'] = pd.NA
            exploded_list.append(new_row.to_dict())
            continue
            
        for po in po_numbers:
            new_row = row.copy()
            new_row['PO_Clean'] = po
            exploded_list.append(new_row.to_dict())

    df_b_final = pd.DataFrame(exploded_list).dropna(subset=['PO_Clean']).drop_duplicates(subset=['PO_Clean'])
    df_b_final['Source'] = 'Import_Doc_B'
    return df_b_final[['PO_Clean', 'ETA', 'Arrival Vessel', 'Arrival Voyage', 'Container', 'Source']]


def process_tri_star_report(df_a):
    """Processes Excel A (TRI-STAR) to detect header, clean ETA, and standardize columns."""
    
    # 1. Header Detection
    keywords_a = ["Order #", "Supplier"]
    header_row_index = detect_header_row(df_a, keywords_a)
    
    # Re-read DataFrame with correct header
    df_a.columns = df_a.iloc[header_row_index]
    df_a = df_a[header_row_index+1:].reset_index(drop=True)
    df_a.columns = [str(col).strip() if col is not None else f'Unnamed_{i}' for i, col in enumerate(df_a.columns)]
    
    st.info(f"Header row detected at index **{header_row_index + 1}** in TRI-STAR REPORT.")

    # 2. Column Standardization
    col_map = {
        'Order #': 'PO',
        'ETA': 'ETA',
        'Arrival Vessel': 'Arrival Vessel',
        'Arrival Voyage': 'Arrival Voyage',
        'Container': 'Container'
    }
    
    # Find the actual column names in df_a
    standardized_df = pd.DataFrame()
    for old_col, new_col in col_map.items():
        if old_col in df_a.columns:
            standardized_df[new_col] = df_a[old_col]
        else:
            # Handle slight variations for Order #
            actual_col = get_col_name(df_a, ['order', 'order #', 'order number']) if old_col == 'Order #' else None
            if actual_col:
                standardized_df[new_col] = df_a[actual_col]
            else:
                standardized_df[new_col] = pd.NA
                st.warning(f"Could not find column **{old_col}** in TRI-STAR REPORT.")
    
    # 3. Cleaning: Drop rows where ETA is invalid
    original_count = len(standardized_df)
    
    def safe_to_datetime(date_series):
        # Attempt to convert to datetime, coercing errors to NaT
        return pd.to_datetime(date_series, errors='coerce')

    standardized_df['ETA_Clean'] = safe_to_datetime(standardized_df['ETA'])
    standardized_df = standardized_df.dropna(subset=['ETA_Clean'])
    
    rows_dropped = original_count - len(standardized_df)
    if rows_dropped > 0:
        st.info(f"Dropped **{rows_dropped}** rows from TRI-STAR REPORT due to invalid ETA values.")
        
    # 4. PO Extraction and Explosion
    exploded_list = []
    for index, row in standardized_df.iterrows():
        po_numbers = normalize_po(row['PO'])
        
        if not po_numbers:
            # Keep original row for unmatched tracking, but set PO to NaN
            new_row = row.copy()
            new_row['PO_Clean'] = pd.NA
            exploded_list.append(new_row.to_dict())
            continue
            
        for po in po_numbers:
            new_row = row.copy()
            new_row['PO_Clean'] = po
            exploded_list.append(new_row.to_dict())

    df_a_final = pd.DataFrame(exploded_list).dropna(subset=['PO_Clean']).drop_duplicates(subset=['PO_Clean'])
    df_a_final['Source'] = 'Tri_Star_A'

    return df_a_final[['PO_Clean', 'ETA', 'Arrival Vessel', 'Arrival Voyage', 'Container', 'Source', 'ETA_Clean']]

# --- Comparison Logic ---

def compare_dataframes(df_a, df_b):
    """Compares the two processed dataframes based on PO_Clean."""
    
    # POs in A and B
    matched_pos = list(set(df_a['PO_Clean']).intersection(set(df_b['PO_Clean'])))
    
    # POs in A but not in B
    unmatched_a_pos = list(set(df_a['PO_Clean']) - set(df_b['PO_Clean']))
    
    # Prepare DataFrames for comparison
    df_a_comp = df_a[df_a['PO_Clean'].isin(matched_pos)].set_index('PO_Clean')
    df_b_comp = df_b[df_b['PO_Clean'].isin(matched_pos)].set_index('PO_Clean')
    
    # Initialize results
    eta_diffs = []
    container_diffs = []
    vessel_diffs = []
    
    for po in matched_pos:
        row_a = df_a_comp.loc[po]
        row_b = df_b_comp.loc[po]
        
        # 1. ETA Comparison
        eta_a_str = row_a['ETA_Clean'].strftime('%Y-%m-%d') if pd.notna(row_a['ETA_Clean']) else 'N/A'
        # Try to parse ETA in B for clean comparison. If it fails, rely on the original string
        try:
            eta_b_clean = pd.to_datetime(row_b['ETA'], errors='coerce')
            eta_b_str = eta_b_clean.strftime('%Y-%m-%d') if pd.notna(eta_b_clean) else str(row_b['ETA'])
        except:
            eta_b_str = str(row_b['ETA'])
        
        # Compare cleaned dates (or date strings if cleaning failed)
        if eta_a_str != eta_b_str:
            eta_diffs.append({
                'PO': po,
                'A_ETA': row_a['ETA'],
                'B_ETA': row_b['ETA'],
                'A_Source_Value': eta_a_str,
                'B_Source_Value': eta_b_str
            })

        # 2. Vessel/Voyage Comparison
        vessel_a = normalize_vessel(row_a['Arrival Vessel'])
        voyage_a = normalize_vessel(row_a['Arrival Voyage'])
        vessel_b = normalize_vessel(row_b['Arrival Vessel'])
        voyage_b = normalize_vessel(row_b['Arrival Voyage'])
        
        if (vessel_a and vessel_b and vessel_a != vessel_b) or \
           (voyage_a and voyage_b and voyage_a != voyage_b):
            vessel_diffs.append({
                'PO': po,
                'A_Vessel': row_a['Arrival Vessel'],
                'A_Voyage': row_a['Arrival Voyage'],
                'B_Vessel': row_b['Arrival Vessel'],
                'B_Voyage': row_b['Arrival Voyage']
            })
            
        # 3. Container Comparison (New Container Number logic)
        num_a, type_a = extract_container_info(row_a['Container'])
        num_b, type_b = extract_container_info(row_b['Container']) # B might have multiple consolidated containers
        
        # Rule 2.3: If A has only type, do nothing
        if num_a is None and type_a is not None:
            continue
            
        # Rule 2.1 & 2.2: A has a container number
        if num_a is not None:
            
            # Check if B's container number is different or missing
            if num_b is None:
                # A has number, B doesn't -> Difference
                container_diffs.append({
                    'PO': po,
                    'A_Container': row_a['Container'],
                    'B_Container': row_b['Container'],
                    'Reason': 'A has container number, B does not.'
                })
            elif num_a != num_b:
                # A and B have different container numbers -> Difference
                 container_diffs.append({
                    'PO': po,
                    'A_Container': row_a['Container'],
                    'B_Container': row_b['Container'],
                    'Reason': 'Different container numbers found.'
                })
            elif type_a is not None and type_b is not None and type_a != type_b:
                # A and B have the same number but different types -> Difference
                container_diffs.append({
                    'PO': po,
                    'A_Container': row_a['Container'],
                    'B_Container': row_b['Container'],
                    'Reason': 'Same container number, different type.'
                })
        
    return {
        'eta_diffs': pd.DataFrame(eta_diffs) if eta_diffs else pd.DataFrame(),
        'unmatched_a': df_a[df_a['PO_Clean'].isin(unmatched_a_pos)][['PO_Clean', 'ETA', 'Container']].rename(columns={'PO_Clean': 'Unmatched PO (TRI-STAR)'}),
        'container_diffs': pd.DataFrame(container_diffs) if container_diffs else pd.DataFrame(),
    }

# --- Streamlit UI and Execution ---

def to_csv_download(df):
    """Converts DataFrame to CSV and returns a download button."""
    csv = df.to_csv(index=False).encode('utf-8')
    return csv

st.set_page_config(layout="wide")

st.title("🚢 TRI-STAR SHIPMENT CHECK LIST")

# File Upload Section
col1, col2 = st.columns(2)

with col1:
    tri_star_file = st.file_uploader(
        "**TRI-STAR SHIPMENT REPORT (Excel A)**", 
        type=['xlsx', 'csv'], 
        accept_multiple_files=True,
        help="Upload the 'AKL Client Order Followup Status...' report."
    )
    
with col2:
    import_doc_files = st.file_uploader(
        "**IMPORT DOC (Excel B)**", 
        type=['xlsx', 'csv'], 
        accept_multiple_files=True,
        help="Upload the 'import_doc_james...' files/sheets."
    )

if tri_star_file and import_doc_files:
    
    st.markdown("---")
    st.subheader("⚙️ Processing Files...")
    
    try:
        # --- 1. Process TRI-STAR REPORT (A) ---
        # Assuming the user uploads only one primary A file, use the first one provided
        # We need the original file name to find the correct sheets in the environment's file list
        tri_star_df_raw = None
        if tri_star_file and tri_star_file[0].name.endswith('.csv'):
             # If it's a single CSV, load it
            tri_star_file[0].seek(0)
            tri_star_df_raw = pd.read_csv(tri_star_file[0])
            original_name_a = tri_star_file[0].name.split(' - ')[0]
        elif tri_star_file:
             # Handle actual excel file object if environment supports it
             st.error("Please upload the file as a CSV/sheet for processing.")
             st.stop()
        
        # Try to find the correct A file in the list if multiple were uploaded (due to environment mock)
        if tri_star_df_raw is None:
             # Find the most likely 'A' file based on keywords, defaulting to the first CSV in the list
             target_a_file = next((f for f in tri_star_file if 'Client - Order Status Summary R.csv' in f.name), None)
             if target_a_file:
                 target_a_file.seek(0)
                 tri_star_df_raw = pd.read_csv(target_a_file)
                 original_name_a = target_a_file.name.split(' - ')[0]
             else:
                 tri_star_file[0].seek(0)
                 tri_star_df_raw = pd.read_csv(tri_star_file[0])
                 original_name_a = tri_star_file[0].name.split(' - ')[0]

        df_a_proc = process_tri_star_report(tri_star_df_raw.copy())
        
        if df_a_proc is None:
            st.error("Failed to process TRI-STAR REPORT (A). Please check the file format.")
            st.stop()

        # --- 2. Process IMPORT DOC (B) ---
        import_doc_dfs = {}
        for f in import_doc_files:
            # Extract sheet name from filename format: "OriginalName.xlsx - Sheet Name.csv"
            try:
                sheet_name_match = re.search(r' - (.*)\.csv$', f.name)
                sheet_name = sheet_name_match.group(1) if sheet_name_match else f.name
                f.seek(0)
                import_doc_dfs[sheet_name] = pd.read_csv(f)
            except Exception as e:
                st.warning(f"Could not read sheet {f.name} for Import Doc: {e}")

        df_b_proc = process_import_doc(import_doc_dfs)

        if df_b_proc is None:
            st.error("Failed to process IMPORT DOC (B). Please check the file format.")
            st.stop()
            
        # --- 3. Run Comparison ---
        st.subheader("🔬 Running Comparison...")
        results = compare_dataframes(df_a_proc, df_b_proc)
        
        eta_diffs = results['eta_diffs']
        unmatched_a = results['unmatched_a']
        container_diffs = results['container_diffs']
        
        
        st.markdown("---")
        st.subheader("✅ Comparison Results")

        # 1. Different in ETA
        st.markdown("#### 1. POs with Different ETA")
        if not eta_diffs.empty:
            st.dataframe(eta_diffs.rename(columns={
                'A_ETA': 'TRI-STAR ETA (Original)',
                'B_ETA': 'IMPORT DOC ETA (Original)',
                'A_Source_Value': 'TRI-STAR ETA (Clean)',
                'B_Source_Value': 'IMPORT DOC ETA (Clean)'
            }), use_container_width=True)
            
            st.download_button(
                label="Download Different ETA CSV",
                data=to_csv_download(eta_diffs),
                file_name="eta_discrepancies.csv",
                mime="text/csv",
                key='dl_eta'
            )
        else:
            st.success("No differences found in ETA for matched POs.")
            st.markdown("<hr>", unsafe_allow_html=True)
            
        # 2. Unmatched PO Number from TRI-STAR
        st.markdown("#### 2. Unmatched POs from TRI-STAR REPORT (Not found in IMPORT DOC)")
        if not unmatched_a.empty:
            st.dataframe(unmatched_a.rename(columns={
                'ETA': 'TRI-STAR ETA',
                'Container': 'TRI-STAR Container'
            }), use_container_width=True)
            
            st.download_button(
                label="Download Unmatched PO CSV",
                data=to_csv_download(unmatched_a),
                file_name="unmatched_po_tri_star.csv",
                mime="text/csv",
                key='dl_unmatched'
            )
        else:
            st.success("All TRI-STAR POs were matched in the IMPORT DOC.")
            st.markdown("<hr>", unsafe_allow_html=True)
            
        # 3. New Container Number (Discrepancies)
        st.markdown("#### 3. Container Discrepancies (New Container Number)")
        if not container_diffs.empty:
            st.dataframe(container_diffs.rename(columns={
                'A_Container': 'TRI-STAR Container',
                'B_Container': 'IMPORT DOC Container'
            }), use_container_width=True)
            
            st.download_button(
                label="Download Container Discrepancy CSV",
                data=to_csv_download(container_diffs),
                file_name="container_discrepancies.csv",
                mime="text/csv",
                key='dl_container'
            )
        else:
            st.success("No container number discrepancies found for matched POs.")
            st.markdown("<hr>", unsafe_allow_html=True)

        st.info("Comparison complete.")
            
    except Exception as e:
        st.error(f"An unexpected error occurred during processing or comparison: {e}")

else:
    st.info("Please upload both the TRI-STAR SHIPMENT REPORT and IMPORT DOC files to start the comparison.")

