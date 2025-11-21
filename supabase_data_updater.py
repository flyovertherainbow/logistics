import logging
from supabase import Client
from fuzzywuzzy import fuzz # Assuming fuzzywuzzy is used for similarity logic
# SUPABASE_TABLE must be defined globally or passed, assuming it's global for simplicity
SUPABASE_TABLE = "companies" 

# --- Existing Function (upload_new_companies) ... [omitted for brevity] ---

def clean_name(name):
    """Placeholder for the company name cleaning logic."""
    # This is a critical component used by get_unique_new_companies
    return str(name).lower().strip().replace('inc.', '').replace('llc', '').replace('co.', '').strip()

def get_unique_new_companies(supabase: Client, unique_suppliers: list):
    """
    Placeholder for the fuzzy matching logic used by upload_new_companies.
    Returns: companies_to_insert, companies_skipped_info
    """
    # In a real app, this fetches all DB names and performs fuzzy matching.
    return unique_suppliers, [] 

# --- NEW FUNCTION: Upload Ports ---

def upload_new_ports(supabase: Client, unique_port_codes: list):
    """
    Fetches country IDs, prepares port data, and inserts new port codes into the 'ports' table.
    
    1. Compares first two letters of port code (e.g., 'CN') to 'countries.code'.
    2. Inserts port_code and corresponding country_id into the 'ports' table.
    3. Uses upsert to skip existing ports.
    
    Args:
        supabase: The initialized Supabase client object.
        unique_port_codes: A list of unique port codes (strings) to insert.
        
    Returns:
        A dictionary containing insertion results and error messages.
    """
    logging.info(f"Starting port data upload for {len(unique_port_codes)} unique codes.")
    
    # --- Step 1: Fetch all country codes and IDs ---
    try:
        # Fetch Country Code and ID (Requirement 2)
        country_response = supabase.table("countries").select("id, code").execute()
        country_map = {item['code'].upper(): item['id'] for item in country_response.data}
        logging.info(f"Fetched {len(country_map)} country records.")
    except Exception as e:
        logging.error(f"Error fetching country data: {e}", exc_info=True)
        # Requirement 5: Display error message
        return {'success': False, 'message': 'Failed to fetch country data.'}

    # --- Step 2: Prepare port data for insertion (Requirement 3) ---
    data_to_insert = []
    ports_without_country = []
    
    for port_code in unique_port_codes:
        if len(port_code) >= 2:
            # Extract first two letters (Requirement 2)
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
             ports_without_country.append(port_code) # Handle codes < 2 chars

    if ports_without_country:
        # Requirement 5: Display error if no country ID found
        logging.warning(f"Skipped {len(ports_without_country)} ports because no matching country code was found: {', '.join(ports_without_country)}")
        
    if not data_to_insert:
        logging.info("No valid port data to insert after country matching.")
        return {'success': True, 'message': 'No valid port codes found for insertion.', 'inserted_count': 0}

    # --- Step 3: Execute the insertion using upsert (Requirement 4) ---
    try:
        # Use upsert(..., on_conflict='port_code') to only insert new ports 
        # (Requirement 4: if port code exists, do nothing)
        response = supabase.table("ports") \
            .upsert(data_to_insert, on_conflict='port_code') \
            .execute()
        
        inserted_records = response.data
        inserted_count = len(inserted_records)
        
        # Requirement 5: Display successful message
        message = f"Successfully inserted {inserted_count} new ports."
        if ports_without_country:
            message += f" (Note: {len(ports_without_country)} ports were skipped due to missing country ID.)"
        
        return {'success': True, 'message': message, 'inserted_count': inserted_count, 'inserted_data': inserted_records}

    except Exception as e:
        # Requirement 5: Display error message
        logging.error(f"An error occurred during Supabase port insertion: {e}", exc_info=True)
        return {'success': False, 'message': f'Database upload failed: {e}'}

# --- Existing Function (upload_new_companies) ---
def upload_new_companies(supabase: Client, unique_suppliers: list):
    """
    Prepares and uploads new unique company names to the 'companies' table,
    setting the 'company_cat' field to '1' for all entries.
    
    Args:
        supabase: The initialized Supabase client object.
        unique_suppliers: A list of supplier names (strings) to insert.
        
    Returns:
        The inserted records (list of dicts) on success, or None on failure.
    """
    
    # --- STEP: Pre-filter the list using similarity logic ---
    companies_to_insert, companies_skipped_info = get_unique_new_companies(supabase, unique_suppliers)
    
    # 1. Prepare the data for insertion
    data_to_insert = []
    
    for name in companies_to_insert:
        data_to_insert.append({
            "company_name": name,      # Inserts the supplier name (original string)
            "company_cat": 1           # Inserts the digit 1
        })

    if not data_to_insert:
        logging.info("No unique companies to insert after cleaning and filtering.")
        
        # 3. Provide user warning even if only filtering happened
        if companies_skipped_info:
            logging.warning("-" * 50)
            logging.warning("WARNING: The following companies were skipped due to high similarity (>= 85%) or being exact matches with existing records:")
            for skip_message in companies_skipped_info:
                logging.warning(f"  - {skip_message}")
            logging.warning("-" * 50)

        # Return an empty list to indicate no insertions, but not an error
        return []

    logging.info(f"Attempting to insert {len(data_to_insert)} records into '{SUPABASE_TABLE}'...")

    # Initialize inserted_records to ensure it exists for the final check
    inserted_records = None 
    
    try:
        # 2. Execute the insertion using .upsert() for conflict resolution
        # 'on_conflict' ensures that if a company_name already exists, it is not inserted again (effectively an insert-only upsert).
        response = supabase.table(SUPABASE_TABLE) \
            .upsert(data_to_insert, on_conflict='company_name') \
            .execute()
        
        inserted_records = response.data

        logging.info(f"Successfully inserted {len(inserted_records)} new companies.")
        
    except Exception as e:
        # Log the error including the full traceback for better debugging
        logging.error(f"An error occurred during Supabase insertion: {e}", exc_info=True)
        return None

    # 3. Provide user warning for skipped companies (after successful insertion)
    if companies_skipped_info:
        logging.warning("-" * 50)
        logging.warning("WARNING: The following companies were skipped due to high similarity (>= 85%) or being exact matches with existing records:")
        for skip_message in companies_skipped_info:
            logging.warning(f"  - {skip_message}")
        logging.warning("-" * 50)
        
    return inserted_records
