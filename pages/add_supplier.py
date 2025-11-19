import streamlit as st
import pandas as pd
import os
import sys
# New Imports for Supabase (Step 2)
from supabase import create_client, Client 

# --- FIX: Add the project root directory to the Python path ---
# This line is kept to ensure this page can easily be expanded later 
# if it needs to import modules from the root.
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
        # Retrieve credentials from the environment variables (first priority) 
        # or st.secrets (second priority - for Streamlit Cloud deployment)
        SUPABASE_URL = os.environ.get("SUPABASE_URL", st.secrets.get("SUPABASE_URL"))
        SUPABASE_KEY = os.environ.get("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY"))

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
    extracts the unique supplier list, and cleans up the dataframe.
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
        return None

    # 2. Find the row index that contains the supplier column header
    header_row_index = -1
    target_names = ['supplier', 'supplier name', 'company name', 'vendor']
    
    for i in range(len(df)):
        # Convert row values to string, lowercase, and check if any contain a target name
        row_str = df.iloc[i].astype(str).str.lower()
        
        # Check if any cell in this row contains one of the target header names
        if row_str.str.contains('|'.join(target_names)).any():
            header_row_index = i
            break

    if header_row_index == -1:
        st.warning("⚠️ Could not find a header row containing 'supplier', 'company name', or 'vendor' in the first 20 rows.")
        return None

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
        return None

    # 4. Identify the exact column name for the supplier
    supplier_column_name = None
    for col in final_df.columns:
        # Check for case-insensitive match with the target names
        if any(name in str(col).lower() for name in target_names):
            supplier_column_name = col
            break

    if supplier_column_name is None:
        st.error("❌ Failed to identify the supplier column after setting the new header. The header row may be malformed.")
        return None
        
    st.info(f"Using column: **{supplier_column_name}** for supplier list extraction.")

    # 5. Get the values, remove duplicates, and drop NaN/empty values
    raw_unique_suppliers = final_df[supplier_column_name].dropna().astype(str).str.strip().unique().tolist()
    
    # --- NEW LOGIC: Exclude names containing "various" ---
    suppliers_to_keep = []
    suppliers_excluded_various = []
    exclusion_keyword = "various"
    
    for name in raw_unique_suppliers:
        if exclusion_keyword in name.lower():
            suppliers_excluded_various.append(name)
        else:
            suppliers_to_keep.append(name)
    
    # Store excluded list in session state for displaying a warning outside this function
    st.session_state['suppliers_excluded_various'] = suppliers_excluded_various
    
    return suppliers_to_keep # Return the filtered list

# --- Main Page Execution ---

# --- Page Title and Introduction ---
st.title("📦 Add Supplier Data (Step 1: File Input)")
st.markdown("Upload your supplier data file below. The system will automatically detect the header row, remove preceding rows, and extract a unique list of suppliers.")

# =========================================================================
# STEP 1: Display Input Field, Handle Upload, and Show Unique List
# =========================================================================
st.subheader("1. Upload File and Process")

# 1. File Uploader Widget
uploaded_file = st.file_uploader(
    "Drag and drop your Excel (.xlsx) or CSV (.csv) file here", 
    type=["xlsx", "csv"],
    help="The file must contain a column with a header like 'Supplier Name', 'Company Name', or 'Vendor'."
)

if uploaded_file is None:
    st.info("Awaiting file upload...")
    st.stop() 

# File is present, proceed to processing
st.success(f"File uploaded successfully: **{uploaded_file.name}**")

# Process the data using the custom function
unique_suppliers_list = find_header_and_process_data(uploaded_file)

if unique_suppliers_list:
    st.markdown("---")
    st.subheader(f"✅ Extracted Supplier List (Total Unique: {len(unique_suppliers_list)})")
    
    # Display the list as a DataFrame for clear visibility and scrolling
    suppliers_df = pd.DataFrame(unique_suppliers_list, columns=["Unique Supplier Name"])
    st.dataframe(suppliers_df, height=300)
    
    st.info("This is the final list that will be checked against the database in the next step.")
    
    # Store the unique list in session state so Step 2 can access it easily
    st.session_state['unique_suppliers_list'] = unique_suppliers_list
    
    # --- WARNING LOGIC (Based on user request) ---
    if 'suppliers_excluded_various' in st.session_state and st.session_state['suppliers_excluded_various']:
        excluded = st.session_state['suppliers_excluded_various']
        st.warning(f"⚠️ **{len(excluded)} Supplier(s) Excluded:** The following names were removed from the list because they contain the keyword 'various' (case-insensitive): \n\n" + ", ".join(excluded))

    
    # =========================================================================
    # NEW: STEP 2: Test Supabase Connection and Read Data
    # =========================================================================
    
    st.markdown("---")
    st.subheader("2. Test Supabase Connection")
    
    # Initialize the Supabase client (cached)
    supabase = init_supabase_client()
    
    if supabase is None:
        st.error("Cannot proceed. Please fix Supabase credentials in `.streamlit/secrets.toml`.")
        # Do not stop here, just prevent database interaction below
    else:
        if st.button("Test Database Connection", help="Click to confirm the connection is active and can read data."):
            with st.spinner("Connecting and querying the 'companies' table..."):
                try:
                    # Fetch a small sample of data (limit 5) from the 'companies' table
                    # This confirms both connectivity and read access to the target table.
                    response = supabase.table("companies").select("*").limit(5).execute()
                    
                    if response.data:
                        st.success("🎉 Connection successful! The application can read data from the 'companies' table.")
                        st.caption("Sample Data from Database:")
                        st.dataframe(pd.DataFrame(response.data))
                        st.session_state['supabase_connected'] = True
                    else:
                        st.info("Connection successful, but the 'companies' table appears to be empty or inaccessible (0 records returned).")
                        st.session_state['supabase_connected'] = True # Connection is still successful
                        
                except Exception as e:
                    st.error(f"Connection Test Failed! Error: {e}")
                    st.error("Possible reasons: Incorrect URL/Key, Network firewall, or the 'companies' table does not exist or has incorrect access policies.")
                    st.session_state['supabase_connected'] = False
