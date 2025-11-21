import streamlit as st
import pandas as pd
import os
import sys
# New Imports for Supabase (Step 2)
from supabase import create_client, Client 
# Import the core update logic (now simplified for companies)
from supabase_data_updater import upload_new_companies, upload_new_ports 

# --- FIX: Add the project root directory to the Python path ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# ---------------------------------------------------------------

# --- Supabase Initialization (Step 2) ---

@st.cache_resource
def init_supabase_client():
    """
    Initializes and caches the Supabase client using credentials from st.secrets.
    This function only runs once due to @st.cache_resource.
    """
    try:
        # Check if st.secrets contains the expected dictionary keys
        if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
            # Fallback check for credentials if they are passed as environment variables
            SUPABASE_URL = os.environ.get("SUPABASE_URL")
            SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
        else:
            SUPABASE_URL = st.secrets["SUPABASE_URL"]
            SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

        if not SUPABASE_URL or not SUPABASE_KEY:
            st.error("Supabase credentials (SUPABASE_URL or SUPABASE_KEY) not found in `secrets.toml` or environment variables.")
            return None
        
        # Create and return the Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
        
    except Exception as e:
        st.error(f"Error initializing Supabase client: {e}")
        return None

# --- Helper Function for Data Cleaning (Advanced Step 1 Logic) ---

def find_header_and_process_data(uploaded_file):
    """
    Reads the file, finds the header row containing 'supplier', sets the header,
    extracts the unique supplier list AND port codes.
    
    Returns: 
        A tuple (suppliers_to_keep, unique_port_codes) or None on failure.
    """
    st.subheader("Processing Data File...")
    
    # 1. Initial read without header for scanning
    try:
        if uploaded_file.name.endswith('.csv'):
            # Read CSV with robust separator detection, reading up to 20 rows max initially
            df = pd.read_csv(uploaded_file, sep=None, engine='python', header=None, nrows=20)
        else: # Assumes Excel (.xlsx)
            df = pd.read_excel(uploaded_file, header=None, nrows=20)
    except Exception as e:
        st.error(f"Error reading the uploaded file initially: {e}")
        return None, None

    # 2. Find the row index that contains the supplier column header
    header_row_index = -1
    target_supplier_names = ['supplier', 'supplier name', 'company name', 'vendor']
    
    for i in range(len(df)):
        # Convert row values to string, lowercase, and check if any contain a target name
        row_str = df.iloc[i].astype(str).str.lower()
        
        # Check if any cell in this row contains one of the target header names
        if row_str.str.contains('|'.join(target_supplier_names)).any():
            header_row_index = i
            break

    if header_row_index == -1:
        st.warning("⚠️ Could not find a header row containing 'supplier', 'company name', or 'vendor' in the first 20 rows.")
        return None, None

    st.success(f"Header row found at index {header_row_index + 1} (0-indexed row {header_row_index}). Discarding preceding rows.")

    # 3. Re-read the file with the correct header index
    uploaded_file.seek(0) # Reset file pointer to the beginning
    try:
        if uploaded_file.name.endswith('.csv'):
            # Read the file again, starting from the identified header row
            final_df = pd.read_csv(uploaded_file, sep=None, engine='python', header=header_row_index)
        else:
            final_df = pd.read_excel(uploaded_file, header=header_row_index)
    except Exception as e:
        st.error(f"Error re-reading file with new header row: {e}")
        return None, None

    # 4. Identify the exact column names for supplier and ports
    supplier_column_name = None
    port_column_names = []
    
    # Keywords for ports (Load, Disch, Code)
    target_port_names = ['load', 'disch', 'port of forwarding of loading code', 'port of discharge code']

    for col in final_df.columns:
        col_lower = str(col).lower()
        # Check for supplier column
        if any(name in col_lower for name in target_supplier_names) and supplier_column_name is None:
            supplier_column_name = col
        # Check for port columns
        if any(name in col_lower for name in target_port_names):
            port_column_names.append(col)


    # --- Supplier extraction
    if supplier_column_name is None:
        st.error("❌ Failed to identify the supplier column after setting the new header.")
        suppliers_to_keep = []
    else:
        st.info(f"Using column: **{supplier_column_name}** for supplier list extraction.")
        # 5. Get the values, remove duplicates, and drop NaN/empty values (Suppliers)
        raw_unique_suppliers = final_df[supplier_column_name].dropna().astype(str).str.strip().unique().tolist()
        
        # --- LOGIC: Exclude names containing "various" ---
        suppliers_to_keep = []
        suppliers_excluded_various = []
        exclusion_keyword = "various"
        
        for name in raw_unique_suppliers:
            if exclusion_keyword in name.lower():
                suppliers_excluded_various.append(name)
            else:
                suppliers_to_keep.append(name)
        
        st.session_state['suppliers_excluded_various'] = suppliers_excluded_various


    # --- Port extraction
    unique_port_codes = []
    if not port_column_names:
        st.warning("⚠️ Could not identify any port code columns ('Load', 'Disch.', 'port of forwarding of loading code', etc.). Skipping port upload.")
    else:
        st.info(f"Using columns: **{', '.join(port_column_names)}** for port code extraction.")
        # Concatenate all port columns into a single series, drop NaNs, strip, and get unique values
        port_series = pd.concat([final_df[col].dropna().astype(str).str.strip() for col in port_column_names])
        # Filter to keep only codes that look like 5-letter UN/LOCODEs (e.g., 'CNBJS', 'USNYC')
        unique_port_codes = port_series.str.upper().unique().tolist()
        # Further clean: filter for common port code length (usually 5 characters) and alphanumeric
        unique_port_codes = [code for code in unique_port_codes if len(code) == 5 and code.isalnum()]
        
    st.session_state['unique_port_codes'] = unique_port_codes # Store for automatic upload

    return suppliers_to_keep, unique_port_codes

# --- Main Page Execution ---

# --- Page Title and Introduction ---
st.title("📦 Add Supplier Data (Step 1: File Input)")
st.markdown("Upload your supplier data file below. The system will automatically detect the header row, remove preceding rows, and extract a unique list of **suppliers and port codes**.")

# =========================================================================
# STEP 1: Display Input Field, Handle Upload, and Show Unique List
# =========================================================================
st.subheader("1. Upload File and Process")

# 1. File Uploader Widget
uploaded_file = st.file_uploader(
    "Drag and drop your Excel (.xlsx) or CSV (.csv) file here", 
    type=["xlsx", "csv"],
    help="The file must contain a column with a header like 'Supplier Name' and columns for ports (e.g., 'Load', 'Disch.')."
)

if uploaded_file is None:
    st.info("Awaiting file upload...")
    st.stop() 

# File is present, proceed to processing
st.success(f"File uploaded successfully: **{uploaded_file.name}**")

# Process the data using the custom function
unique_suppliers_list, unique_port_codes = find_header_and_process_data(uploaded_file)

# Initialize Supabase client early for database operations
supabase = init_supabase_client()


if unique_suppliers_list is not None: # Check against None in case of file reading failure
    
    # --- AUTOMATIC PORT UPLOAD (No button needed) ---
    st.markdown("---")
    st.subheader("Automatic: Check and Insert Ports/Countries")

    # Display extracted port codes list/count 
    if unique_port_codes:
        st.info(f"**Extracted Port Codes:** Found {len(unique_port_codes)} unique 5-letter codes from file.")
        with st.expander("Show Extracted Codes (Raw List)"):
            # Display up to 20 codes or all codes if fewer than 20
            st.code(", ".join(unique_port_codes[:20]) + ("..." if len(unique_port_codes) > 20 else ""))
    else:
        st.info("No valid port codes were extracted from the file.") 


    if supabase is None:
        st.error("Cannot perform automatic port upload. Supabase client is not initialized.")
    elif not unique_port_codes:
        pass
    elif 'port_upload_complete' not in st.session_state:
        # Check if the port upload has already run in the current session state
        with st.spinner(f"Matching {len(unique_port_codes)} ports to country codes and inserting..."):
            port_result = upload_new_ports(supabase, unique_port_codes)
            st.session_state['port_upload_complete'] = True # Mark as completed

        # --- Display Results ---
        if port_result['success']:
            # Success Path (0 or more insertions)
            inserted_codes = port_result.get('inserted_codes', [])
            
            if len(inserted_codes) > 0:
                st.success(f"🎉 Port Check/Upload Success! {port_result['message']}")
                
                # Use the new explicit return key
                st.markdown(f"**Newly Inserted Port Codes:** `{', '.join(inserted_codes)}`") 

                with st.expander("Show All Newly Inserted Codes"):
                    st.text_area("Codes:", value='\n'.join(inserted_codes), height=150)
            else:
                st.info("👍 Processing complete. **No new port added** (all extracted codes either existed in the database or were invalid/missing country codes).")
            
            # Check for skipped ports due to missing country code (Warning after Success)
            if port_result.get('ports_without_country') and len(port_result['ports_without_country']) > 0:
                skipped_codes = port_result['ports_without_country']
                st.warning(
                    f"⚠️ **{len(skipped_codes)} Port(s) Skipped (Missing Country Code):** "
                    f"The following codes could not be matched to an existing country and were not inserted: "
                    f"`{', '.join(skipped_codes)}`"
                )

        else:
            # Failure Path (Database error or country fetch error)
            error_codes = port_result.get('attempted_codes', unique_port_codes)
            
            st.error(f"❌ Port Database Upload Failed: {port_result['message']}")
            
            if error_codes:
                 st.markdown(
                    f"**The following port codes were in the batch that failed insertion:** "
                    f"`{', '.join(error_codes)}`"
                )
            else:
                st.markdown(
                    "No specific codes could be identified as the source of the failure, but the batch process was aborted."
                )

            st.error("Ensure your 'countries' and 'ports' tables exist and have correct RLS policies for SELECT and INSERT.")
    else:
        st.info("Port codes have already been processed and uploaded in this session.")


    # --- Display SUPPLIER Results (Always after port processing) ---
    st.markdown("---")
    st.subheader(f"✅ Extracted Supplier List (Total Unique: {len(unique_suppliers_list)})")
    
    if unique_suppliers_list:
        # Display the list as a DataFrame for clear visibility and scrolling
        suppliers_df = pd.DataFrame(unique_suppliers_list, columns=["Unique Supplier Name"])
        st.dataframe(suppliers_df, height=300)
        
        st.info("This list is ready for insertion. The database's unique constraint will automatically skip existing names.")
        
        # --- WARNING LOGIC (For 'various' exclusion) ---
        if 'suppliers_excluded_various' in st.session_state and st.session_state['suppliers_excluded_various']:
            excluded = st.session_state['suppliers_excluded_various']
            st.warning(f"⚠️ **{len(excluded)} Supplier(s) Excluded:** The following names were removed because they contain the keyword 'various': \n\n" + ", ".join(excluded))
    else:
        st.info("No valid supplier names found in the extracted column.")

    
    # =========================================================================
    # STEP 2: Test Supabase Connection and Read Data (Unchanged)
    # =========================================================================
    
    st.markdown("---")
    st.subheader("2. Test Supabase Connection")
    
    if supabase is None:
        st.error("Cannot proceed. Supabase client is not initialized.")
    else:
        if st.button("Test Database Connection", help="Click to confirm the connection is active and can read data."):
            with st.spinner("Connecting and querying the 'companies' table..."):
                try:
                    # Fetch a small sample of data (limit 5) from the 'companies' table
                    response = supabase.table("companies").select("*").limit(5).execute()
                    
                    if response.data:
                        st.success("🎉 Connection successful! The application can read data from the 'companies' table.")
                        st.caption("Sample Data from Database:")
                        st.dataframe(pd.DataFrame(response.data))
                        st.session_state['supabase_connected'] = True
                    else:
                        st.info("Connection successful, but the 'companies' table appears to be empty or inaccessible (0 records returned).")
                        st.session_state['supabase_connected'] = True 
                        
                except Exception as e:
                    st.error(f"Connection Test Failed! Error: {e}")
                    st.session_state['supabase_connected'] = False
                    
    # =========================================================================
    # STEP 3: Upload New Companies (Instant Insert)
    # =========================================================================
    
    st.markdown("---")
    st.subheader("3. Upload Companies (DB Deduplication)")
    
    total_count = len(unique_suppliers_list)
    
    if supabase is None:
        st.error("Cannot upload companies. Supabase client is not initialized.")
    elif not unique_suppliers_list:
        st.info("No unique suppliers found to upload after processing the file.")
    else:
        
        # Button shows the total number of unique names extracted from the file
        if st.button(f"🚀 Upload ALL {total_count} Suppliers (Check DB for Duplicates)", type="primary"):
            with st.spinner(f"Attempting to insert {total_count} suppliers..."):
                
                # Call the core logic function
                company_result = upload_new_companies(supabase, unique_suppliers_list)
                
            # --- Display Post-Upload Results ---
            if company_result['success']:
                inserted_names = company_result.get('inserted_names', [])
                inserted_count = len(inserted_names)
                
                st.balloons()
                st.success(f"🎉 Success! {company_result['message']}")
                
                if inserted_count > 0:
                    st.subheader(f"Newly Inserted Company Names ({inserted_count})")
                    st.markdown(f"`{', '.join(inserted_names[:10])}`" + ("..." if len(inserted_names) > 10 else ""))
                    with st.expander("Show ALL Newly Inserted Names"):
                        st.text_area("Names:", value='\n'.join(inserted_names), height=200)

            else:
                # Failure path
                failed_names = company_result.get('failed_names', [])
                st.error(f"❌ Database upload failed! {company_result['message']}")
                
                if failed_names:
                    st.warning(f"The upload batch contained {len(failed_names)} names, which may have contributed to the failure.")
                    with st.expander("Show names in the failed batch"):
                        st.text_area("Failed Batch Names:", value='\n'.join(failed_names), height=200)
                
                st.info("Ensure your 'companies' table exists and has correct RLS policies for INSERT and the 'company_name' column is correctly defined.")
