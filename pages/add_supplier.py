import logging
import re
from supabase import create_client, Client
# IMPORTANT: This script requires the fuzzywuzzy library for similarity checks.
# Install with: pip install fuzzywuzzy[speedup]
from fuzzywuzzy import fuzz

# --- Configuration ---
# Your Supabase client initialization should be here (assumed to be available)
# Example:
SUPABASE_URL = "https://efrrkyperrzqirjnuqxt.supabase.co"
SUPABASE_KEY = "sb_publishable_9bbv61MeFOakyKun_SNkSQ_j9cgkWqh"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Use your new table name
SUPABASE_TABLE = 'companies'
logging.basicConfig(level=logging.INFO)

def clean_name(name: str) -> str:
    """
    Normalizes a company name for comparison.
    Converts to lowercase, removes leading/trailing whitespace, and removes common 
    legal suffixes and punctuation to facilitate better matching of similar names.
    """
    if not isinstance(name, str):
        return ""
    
    # Convert to lowercase and strip whitespace
    cleaned = name.lower().strip()
    
    # Optionally remove common suffixes (e.g., corp, llc, inc, ltd)
    # This is a simple way to deal with 'Acme Corp' vs 'Acme'
    suffixes = [r'\s+corp\s*$', r'\s+ltd\s*$', r'\s+inc\s*$', r'\s+llc\s*$', r'\s+co\s*$', r'\s+s\.a\.\s*$']
    for suffix in suffixes:
        cleaned = re.sub(suffix, '', cleaned, flags=re.IGNORECASE)
    
    # Remove all non-alphanumeric characters (keeps spaces)
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    
    return cleaned.strip()

def get_unique_new_companies(supabase: Client, new_suppliers: list) -> tuple[list, list]:
    """
    Fetches existing company names and compares them against the new supplier list 
    using fuzzy matching (85% similarity threshold) to find truly new companies.
    
    Args:
        supabase: The initialized Supabase client object.
        new_suppliers: A list of supplier names (strings) to check.
        
    Returns:
        A tuple: (list of original company names to insert, list of skipped company names with reason).
    """
    logging.info("Fetching existing company names for de-duplication and fuzzy matching.")
    
    # 1. Fetch and process existing data
    existing_companies = []
    try:
        # Fetch only the company_name column
        response = supabase.table(SUPABASE_TABLE).select("company_name").execute()
        if response.data:
            for record in response.data:
                original_name = record.get("company_name", "")
                if original_name:
                    existing_companies.append({
                        "original": original_name,
                        "cleaned": clean_name(original_name)
                    })
        
        logging.info(f"Found {len(existing_companies)} companies for fuzzy comparison in the database.")

    except Exception as e:
        logging.error(f"Error fetching existing companies for de-duplication: {e}")
        # If fetch fails, bypass similarity check and rely on DB conflict resolution
        return new_suppliers, []

    # 2. Filter the new supplier list
    companies_to_insert = []
    companies_skipped_info = []
    
    # Set to track cleaned names *in the current batch* to prevent internal batch duplicates
    current_batch_cleaned_names = set() 
    
    SIMILARITY_THRESHOLD = 85

    for original_name in new_suppliers:
        cleaned_new_name = clean_name(original_name)
        
        if not cleaned_new_name:
            continue

        # Check against internal batch duplicates first
        if cleaned_new_name in current_batch_cleaned_names:
            logging.debug(f"Skipping '{original_name}' (internal duplicate in this batch).")
            continue
        
        # Perform Fuzzy Matching against all existing names
        best_match_name = None
        max_ratio = 0
        
        for existing_company in existing_companies:
            # Use fuzz.ratio on the cleaned strings for best results
            ratio = fuzz.ratio(cleaned_new_name, existing_company["cleaned"])
            if ratio > max_ratio:
                max_ratio = ratio
                best_match_name = existing_company["original"]
                
                # Optimization: if we hit 100%, we can stop searching this name
                if max_ratio == 100:
                    break
        
        if max_ratio >= SIMILARITY_THRESHOLD:
            # Skip due to similarity threshold
            companies_skipped_info.append(f"'{original_name}' (Similarity: {max_ratio}%, matched with '{best_match_name}')")
            current_batch_cleaned_names.add(cleaned_new_name)
        else:
            # New company to insert
            companies_to_insert.append(original_name)
            current_batch_cleaned_names.add(cleaned_new_name)

    logging.info(f"Filtered to {len(companies_to_insert)} truly unique companies after fuzzy matching.")
    return companies_to_insert, companies_skipped_info


def upload_new_companies(supabase: Client, unique_suppliers: list):
    """
    Prepares and uploads new unique company names to the 'companies' table,
    setting the 'company_cat' field to '1' for all entries, and handling similarity.
    
    Args:
        supabase: The initialized Supabase client object.
        unique_suppliers: A list of supplier names (strings) to insert.
    """
    
    # --- NEW STEP: Pre-filter the list using similarity logic ---
    companies_to_insert, companies_skipped_info = get_unique_new_companies(supabase, unique_suppliers)
    
    # 1. Prepare the data for insertion
    data_to_insert = []
    
    for name in companies_to_insert:
        data_to_insert.append({
            "company_name": name,      # Inserts the supplier name (original string)
            "company_cat": 1           # Inserts the digit 1 as requested
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

        return

    logging.info(f"Attempting to insert {len(data_to_insert)} records into '{SUPABASE_TABLE}'...")

    # Initialize inserted_records to ensure it exists for the final check
    inserted_records = None 
    
    try:
        # 2. Execute the insertion
        response = supabase.table(SUPABASE_TABLE) \
            .insert(data_to_insert) \
            .on_conflict('company_name') \
            .execute()
        
        inserted_count = len(response.data) if response.data else 0
        inserted_records = response.data

        logging.info(f"Successfully inserted {inserted_count} new companies.")
        
    except Exception as e:
        logging.error(f"An error occurred during Supabase insertion: {e}")
        return None

    # 3. Provide user warning for skipped companies (after successful insertion)
    if companies_skipped_info:
        logging.warning("-" * 50)
        logging.warning("WARNING: The following companies were skipped due to high similarity (>= 85%) or being exact matches with existing records:")
        for skip_message in companies_skipped_info:
            logging.warning(f"  - {skip_message}")
        logging.warning("-" * 50)
        
    return inserted_records

# --- Example Usage (Requires actual Supabase setup to run) ---
# Example list of unique suppliers
# unique_suppliers_list = ["Acme Corp.", "Beta Solutions LLC", "Acme", "New Supplier A", "Acme Corporation"] 
# 
# If "Acme Corp" exists in DB:
# - "Acme Corp." will be skipped (Exact match on cleaned name)
# - "Acme" will be skipped (High similarity match)
# - "Acme Corporation" will be skipped (High similarity match)

# You would call this function after initializing your 'supabase' client:
# inserted_records = upload_new_companies(supabase, unique_suppliers_list)
# print(inserted_records)
