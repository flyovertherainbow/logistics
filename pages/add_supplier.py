import streamlit as st
import pandas as pd
import os
import sys

# IMPORTANT: These imports rely on the Supabase client and the utility function 
# being available globally or importable. Since the client setup is already 
# in streamlit_app.py, we will duplicate the client setup here for standalone page functionality.
# We also rely on the utility file:
from supabase import create_client, Client
from supabase_data_updater import upload_new_companies

# --- Supabase Initialization (Copied from streamlit_app.py for page execution) ---
try:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", st.secrets.get("SUPABASE_URL"))
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY"))
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        supabase = None
        st.error("Supabase credentials not found. Cannot connect to database.")
    else:
        # Client initialization
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Error initializing Supabase client. Please check your network or configuration. Error: {e}")
    sys.exit()

# --- Page Title and Introduction ---
st.title("📦 Add Supplier Data")
st.markdown("Use this page to upload a file containing new supplier names for de-duplication and insertion into the `companies` table.")

if supabase is None:
    st.warning("Database features are disabled due to missing Supabase credentials.")


# =========================================================================
# STEP 1: Display Input Field, Handle Upload, and Show DataFrame
# =========================================================================
st.subheader("Step 1: Upload File and Select Company Column")

# 1. File Uploader Widget (The drag-and-drop element)
uploaded_file = st.file_uploader(
    "Drag and drop your Excel (.xlsx) or CSV (.csv) file here", 
    type=["xlsx", "csv"],
    help="The file must contain a column with the company/supplier names."
)

if uploaded_file is None:
    st.info("Awaiting file upload...")
    st.stop() # Stop execution if no file is present

# File is present, proceed to reading and displaying
st.success(f"File uploaded successfully: **{uploaded_file.name}**")

try:
    if uploaded_file.name.endswith('.csv'):
        # Read CSV with robust separator detection
        df = pd.read_csv(uploaded_file, sep=None, engine='python')
    else: # Assumes Excel (.xlsx)
        df = pd.read_excel(uploaded_file)

    st.subheader("Data Preview (First 5 Rows)")
    st.dataframe(df.head())
    
    # Select the company name column
    st.info("Please select the column that contains the unique Company/Supplier Names.")
    column_options = df.columns.tolist()
    company_column = st.selectbox(
        "Select Company Name Column",
        options=column_options
    )
    
except Exception as e:
    st.error(f"An error occurred while reading or processing the file. Check if it's a valid Excel/CSV structure. Error: {e}")
    st.stop()


# =========================================================================
# STEP 2: Test Supabase Connection and Read Data
# =========================================================================
st.markdown("---")
st.subheader("Step 2: Database Connection Test")

if supabase:
    if st.button("Test Database Connection & Read Sample Data"):
        with st.spinner("Connecting to Supabase..."):
            try:
                # Read 5 records from the 'companies' table for a connection test
                response = supabase.table('companies').select("company_name, company_cat").limit(5).execute()
                
                if response.data:
                    st.success("✅ Supabase connection successful!")
                    st.info(f"Successfully fetched a sample of {len(response.data)} existing companies:")
                    st.dataframe(pd.DataFrame(response.data))
                else:
                    st.warning("⚠️ Connected to Supabase, but no records were found in the 'companies' table.")
            except Exception as e:
                st.error(f"❌ Connection or read failed. Check permissions/table name. Error: {e}")
                st.stop()
else:
    st.warning("Database test skipped: Supabase client is not initialized.")


# =========================================================================
# STEP 3: Save Data into the Database
# =========================================================================
st.markdown("---")
st.subheader("Step 3: Process and Upload Data")

if supabase and company_column:
    if st.button("🚀 Process & Upload New Companies to Database", type="primary"):
        with st.spinner("Processing file, de-duplicating, and uploading..."):
            
            # Extract the list of unique supplier names from the selected column
            supplier_list = df[company_column].dropna().unique().tolist()
            
            # Call the core logic function from supabase_data_updater.py
            inserted_records = upload_new_companies(supabase, supplier_list)

        # --- Display Final Results ---
        if inserted_records is not None:
            if inserted_records:
                st.balloons()
                st.success(f"✅ Successfully inserted **{len(inserted_records)}** new unique companies into the database!")
                st.subheader("Newly Inserted Records")
                st.dataframe(pd.DataFrame(inserted_records))
            else:
                st.info("👍 Processing complete. No new unique companies were inserted after similarity checks (or all were already present).")
        else:
            st.error("❌ Failed to process or upload data. Check the application logs for connection or database errors.")
            
        st.warning("If the number of inserted records is less than expected, it's likely due to fuzzy matching (>= 85% similarity) with existing companies. Check the console logs for skipped records.")

elif not supabase:
    st.error("Cannot upload data as Supabase connection failed in Step 2.")
elif not company_column:
    st.warning("Please select the correct Company Name Column in Step 1 before proceeding.")
