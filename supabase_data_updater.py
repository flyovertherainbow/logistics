import logging
from supabase import Client
import sys
import os

# Assuming SUPABASE_TABLE is defined globally or passed
SUPABASE_TABLE = "companies" 

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
