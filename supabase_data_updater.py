import logging
from supabase import Client
import sys
import os
import pandas as pd # Import pandas for the new function

# Assuming SUPABASE_TABLE is defined globally or passed
SUPABASE_TABLE = "companies" 

# --- NEW FUNCTION: Data Cleaning and Extraction ---

def extract_port_codes_and_suppliers(uploaded_file, file_type: str) -> dict:
    """
    Reads an uploaded logistics report file, identifies the correct header row
    and column names based on known patterns, and extracts unique port codes 
    and supplier names.

    Args:
        uploaded_file: The file object from Streamlit's st.file_uploader.
        file_type: 'csv' or 'xlsx'.

    Returns:
        A dictionary containing:
        - 'success': bool
        - 'message': str
        - 'unique_port_codes': list of str (or empty list)
        - 'unique_suppliers': list of str (or empty list)
    """
    
    # 1. Define possible column names for port codes and suppliers across different report formats
    PORT_COLUMN_MAP = {
        # File 1 & 3 example (assuming "port/terminal of loading code" is the target for file 3)
        "port of discharge code": "DISCHARGE",
        "port/terminal of loading code": "LOADING",
        # File 2 example
        "load": "LOADING",
        "disch.": "DISCHARGE",
        # File 3 example
        "port of destination": "DISCHARGE",
        "port of origin": "LOADING",
        # Fallback names found in some snippets
        "port of destination": "DISCHARGE",
        "port of origin": "LOADING",
    }
    SUPPLIER_COLUMN_NAMES = ["supplier", "supplier name", "shipper name", "contractorcode"]

    try:
        # 2. Find the actual header row (based on "Supplier" or "Suppluer name")
        # We need to read the first few rows as plain text to find the header
        
        # Reset file pointer to the beginning
        uploaded_file.seek(0)
        
        # Read file into lines (first 50 lines should be enough)
        # Use io.StringIO for CSV or load into memory for Excel
        if file_type == 'csv':
            import io
            file_content = uploaded_file.read().decode('utf-8')
            lines = file_content.splitlines()
        else: # xlsx
            # For Excel, we must read rows iteratively which is less efficient,
            # but usually the report structure is consistent. We'll use pandas read_excel.
            # We'll rely on the pandas functionality to infer the header row later.
            lines = None 
            
        header_row_index = -1
        
        if lines:
            # Look for the header row index containing a clear Supplier column
            for i, line in enumerate(lines[:50]):
                # Normalize line for search (case-insensitive, remove commas for general check)
                normalized_line = line.lower().replace('"', '').replace("'", "")
                
                # Check for "supplier", "shipper name", or common misspellings/variants
                if "supplier" in normalized_line or "shipper name" in normalized_line or "contractorcode" in normalized_line:
                    header_row_index = i
                    break
        
        # 3. Read the file into a DataFrame using the determined header
        
        # Reset file pointer again before handing off to pandas
        uploaded_file.seek(0)
        
        if file_type == 'csv':
            # Use header_row_index + 1 because pandas header index is 0-based from the start of the file
            df = pd.read_csv(uploaded_file, header=header_row_index if header_row_index != -1 else 0, sep=None, engine='python')
        else: # xlsx
             # For Excel, try to infer the header row index (Excel often has the header on the first sheet)
             # If we couldn't find it manually, pandas defaults to the first row (index 0).
             df = pd.read_excel(uploaded_file, header=header_row_index if header_row_index != -1 else 0)


        # 4. Standardize Column Names
        # Create a mapping from current column names (case-insensitive) to normalized names
        column_map = {}
        port_columns = []
        supplier_column = None
        
        # Normalize all DataFrame columns to lowercase for matching
        normalized_df_columns = {col.strip().lower(): col for col in df.columns}
        
        # Find Port Columns
        for current_name_lower, canonical_name in PORT_COLUMN_MAP.items():
            if current_name_lower in normalized_df_columns:
                original_name = normalized_df_columns[current_name_lower]
                port_columns.append(original_name)
                logging.info(f"Found Port Column: '{original_name}' (Type: {canonical_name})")

        # Find Supplier Column
        for name in SUPPLIER_COLUMN_NAMES:
            if name in normalized_df_columns:
                supplier_column = normalized_df_columns[name]
                logging.info(f"Found Supplier Column: '{supplier_column}'")
                break
        
        if not port_columns or not supplier_column:
            missing_cols = []
            if not port_columns:
                missing_cols.append("Port Code (e.g., Load/Discharge)")
            if not supplier_column:
                missing_cols.append("Supplier Name")
            return {
                'success': False,
                'message': f"Could not find required columns in the file: {', '.join(missing_cols)} using any known aliases. Please check the file format.",
                'unique_port_codes': [],
                'unique_suppliers': []
            }


        # 5. Extract Unique Data
        
        # Extract unique Port Codes
        all_port_codes = pd.Series(dtype=str)
        for col in port_columns:
            # Concatenate all non-null values from all identified port columns
            all_port_codes = pd.concat([all_port_codes, df[col].dropna().astype(str).str.strip()])
            
        # Filter to ensure only 5-character UN/LOCODEs are kept (AABBBL, e.g., CNSHA)
        # Assuming port codes are always 5 uppercase letters, filtering out garbage data.
        unique_port_codes = all_port_codes[all_port_codes.str.len() == 5].str.upper().unique().tolist()
        
        # Extract unique Supplier Names (dropna and unique)
        unique_suppliers = df[supplier_column].dropna().astype(str).str.strip().unique().tolist()

        return {
            'success': True,
            'message': f"Successfully extracted {len(unique_suppliers)} unique suppliers and {len(unique_port_codes)} unique port codes.",
            'unique_port_codes': unique_port_codes,
            'unique_suppliers': unique_suppliers
        }

    except Exception as e:
        logging.error(f"Error during file processing: {e}", exc_info=True)
        return {
            'success': False,
            'message': f"Failed to read or process the file. Error: {e}",
            'unique_port_codes': [],
            'unique_suppliers': []
        }
# --- Modified Function: Upload Ports (Returns inserted_codes list) ---

def upload_new_ports(supabase: Client, unique_port_codes: list):
    """
    Fetches country IDs, prepares port data, and inserts new port codes into the 'ports' table.
    
    1. Compares first two letters of port code (e.g., 'CN') to 'countries.code'.
    2. Inserts port_code and corresponding country_id into the 'ports' table.
    3. Uses upsert(..., on_conflict='port_code') to skip existing ports (ensuring no duplicates).
    
    Args:
        supabase: The initialized Supabase client object.
        unique_port_codes: A list of unique port codes (strings) to insert.
        
    Returns:
        A dictionary containing insertion results and error messages, including lists of codes that were skipped or failed.
    """
    logging.info(f"Starting port data upload for {len(unique_port_codes)} unique codes.")
    
    # Initialize error/skipped lists
    ports_without_country = []
    
    # --- Step 1: Fetch all country codes and IDs ---
    try:
        # Fetch Country Code and ID (Requirement 2)
        country_response = supabase.table("countries").select("id, code").execute()
        country_map = {item['code'].upper(): item['id'] for item in country_response.data}
        logging.info(f"Fetched {len(country_map)} country records.")
    except Exception as e:
        logging.error(f"Error fetching country data: {e}", exc_info=True)
        return {
            'success': False, 
            'message': 'Failed to fetch country data.',
            'inserted_count': 0,
            'attempted_codes': unique_port_codes 
        }

    # --- Step 2: Prepare port data for insertion (Requirement 3) ---
    data_to_insert = []
    
    for port_code in unique_port_codes:
        if len(port_code) >= 2:
            country_code = port_code[:2].upper()
            country_id = country_map.get(country_code)
            
            if country_id is not None:
                data_to_insert.append({
                    "port_code": port_code,
                    "country_id": country_id
                })
            else:
                ports_without_country.append(port_code)
        else:
             ports_without_country.append(port_code)

    attempted_codes_for_db = [item['port_code'] for item in data_to_insert]

    if not data_to_insert:
        logging.info("No valid port data to insert after country matching.")
        return {
            'success': True, 
            'message': 'No valid port codes found for insertion.', 
            'inserted_count': 0, 
            'inserted_codes': [], # Explicitly returning empty list
            'ports_without_country': ports_without_country
        }

    # --- Step 3: Execute the insertion using upsert (Requirement 4) ---
    try:
        # Use upsert(..., on_conflict='port_code') to only insert new ports 
        # (This is the mechanism for avoiding duplicates on the 'port_code' column)
        response = supabase.table("ports") \
            .upsert(data_to_insert, on_conflict='port_code') \
            .execute()
        
        inserted_records = response.data
        inserted_count = len(inserted_records)
        # Extract the codes of the newly inserted records
        inserted_codes = [r['port_code'] for r in inserted_records] 
        
        message = f"Successfully inserted {inserted_count} new ports."
        
        return {
            'success': True, 
            'message': message, 
            'inserted_count': inserted_count, 
            'inserted_codes': inserted_codes, # NEW: Returning the list of inserted codes
            'ports_without_country': ports_without_country
        }

    except Exception as e:
        logging.error(f"An error occurred during Supabase port insertion: {e}", exc_info=True)
        return {
            'success': False, 
            'message': f'Database upload failed: {e}',
            'inserted_count': 0,
            'attempted_codes': attempted_codes_for_db
        }

# --- Modified Function: Upload Companies (Instant Insert) ---
def upload_new_companies(supabase: Client, unique_suppliers_list: list):
    """
    Prepares and uploads all unique company names to the 'companies' table,
    relying on the table's UNIQUE constraint on 'company_name' to prevent duplicates.
    """
    
    # 1. Prepare the data for insertion
    data_to_insert = []
    for name in unique_suppliers_list:
        data_to_insert.append({
            "company_name": name,      # Inserts the supplier name (original string)
            "company_cat": 1           # Inserts the digit 1
        })
    
    attempted_names = unique_suppliers_list # All names we try to insert

    if not data_to_insert:
        return {
            'success': True, 
            'message': 'No companies provided for insertion.',
            'inserted_names': [],
        }

    logging.info(f"Attempting to upsert {len(data_to_insert)} records into '{SUPABASE_TABLE}'...")

    try:
        # 2. Execute the insertion using .upsert() for conflict resolution
        response = supabase.table(SUPABASE_TABLE) \
            .upsert(data_to_insert, on_conflict='company_name') \
            .execute()
        
        inserted_records = response.data
        inserted_names = [r['company_name'] for r in inserted_records]
        
        # Calculate how many were skipped due to existing UNIQUE constraint
        inserted_count = len(inserted_names)
        skipped_count = len(attempted_names) - inserted_count
        
        message = (
            f"Successfully inserted {inserted_count} new companies." 
            + (f" ({skipped_count} existing companies were skipped automatically.)" if skipped_count > 0 else "")
        )

        return {
            'success': True, 
            'message': message, 
            'inserted_names': inserted_names,
        }
        
    except Exception as e:
        # Log the error including the full traceback
        logging.error(f"An error occurred during Supabase insertion: {e}", exc_info=True)
        
        # Return the names that were in the batch that failed
        return {
            'success': False, 
            'message': f'Database upload failed. Error details: {e}',
            'failed_names': attempted_names,
        }
