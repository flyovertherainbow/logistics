SUPABASE_URL = "https://efrrkyperrzqirjnuqxt.supabase.co"
SUPABASE_KEY = "sb_publishable_9bbv61MeFOakyKun_SNkSQ_j9cgkWqh"


import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
import sys
# Import the custom utility functions from your existing file
from supabase_data_updater import upload_new_companies

# --- Supabase Initialization (Placeholder for Configuration) ---
# NOTE: This block is crucial.
try:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", st.secrets.get("SUPABASE_URL"))
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY"))
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_KEY in your secrets.")
        supabase = None
    else:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Error initializing Supabase client. Error: {e}")
    sys.exit()

# --- Page Navigation Functions ---

def navigate_to(page_name):
    """Function to change the current page in session state."""
    st.session_state.page = page_name

def show_home_page():
    """
    The main landing page showing a list of functions/features.
    """
    st.title("🏡 Logistics Management System")
    st.markdown("Welcome back! Select a function below to manage your data.")
    
    st.subheader("Available Functions")
    
    # Use columns to present features cleanly
    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("Function 1: Data Upload")
        # This button is what the user clicks to see the drag-and-drop element
        if st.button("➕ Add Supplier Data", key="add_supplier_btn", help="Upload a new Excel/CSV file to update the companies list."):
            navigate_to("Add Supplier")

    with col2:
        st.info("Function 2: View Metrics")
        if st.button("📊 View Dashboard", key="view_dashboard_btn", help="See key performance indicators and visualizations."):
            navigate_to("Dashboard")

    with col3:
        st.info("Function 3: Future Feature")
        st.button("⚙️ Configuration", disabled=True, help="Coming soon...")
        
    st.markdown("---")
    st.write("Current Supabase Connection Status: **Ready**")

def show_data_uploader_page(supabase: Client):
    """
    Displays the UI for file upload and database update logic (The 'Add Supplier' page).
    """
    st.title("📦 Add Supplier Data (Company Uploader)")
    st.markdown("Upload your latest supplier list to check for new and unique companies before inserting them into the Supabase database.")
    
    if supabase is None:
        st.error("Cannot access this feature. Supabase client failed to initialize.")
        return

    # 1. File Uploader Widget
    # This is the drag-and-drop element the user expects to see
    uploaded_file = st.file_uploader(
        "Drag and drop your Excel (.xlsx) or CSV (.csv) file here", 
        type=["xlsx", "csv"],
        help="The file must contain a column with the company/supplier names."
    )

    # 2. Main Processing Logic
    if uploaded_file is not None:
        st.success(f"File uploaded successfully: **{uploaded_file.name}**")
        
        # Check file type and read it using pandas
        try:
            if uploaded_file.name.endswith('.csv'):
                # Added robust separator detection for CSV
                df = pd.read_csv(uploaded_file, sep=None, engine='python')
            else: # Assumes Excel (.xlsx)
                df = pd.read_excel(uploaded_file)

            # Display the first few rows for confirmation
            st.subheader("Data Preview")
            st.dataframe(df.head())
            
            # --- Crucial Step: Identify the Company Name Column ---
            st.info("Please select the column that contains the unique Company/Supplier Names.")
            
            column_options = df.columns.tolist()
            company_column = st.selectbox(
                "Select Company Name Column",
                options=column_options
            )

            # Check if processing button is pressed AND a valid column is selected
            if company_column and st.button("Process & Upload New Companies", type="primary"):
                with st.spinner("Processing file, de-duplicating, and uploading to Supabase..."):
                    # Extract the list of unique supplier names from the selected column
                    supplier_list = df[company_column].dropna().unique().tolist()
                    
                    # Call the core logic function from supabase_data_updater.py
                    inserted_records = upload_new_companies(supabase, supplier_list)

                # --- Display Results ---
                if inserted_records is not None:
                    if inserted_records:
                        st.balloons()
                        st.success(f"✅ Successfully inserted **{len(inserted_records)}** new unique companies into the database!")
                        # Display the newly inserted records
                        st.subheader("Newly Inserted Records")
                        st.dataframe(pd.DataFrame(inserted_records))
                    else:
                        st.info("👍 Processing complete. No new unique companies were inserted after similarity checks (or all were already present).")
                else:
                    st.error("❌ Failed to process or upload data. Check console logs for connection or database errors.")
                    
                st.warning("Details on skipped records (due to similarity) are available in the application logs (console).")


        except Exception as e:
            st.error(f"An error occurred while reading or processing the file. Error: {e}")

    else:
        st.info("Awaiting file upload...")

def show_dashboard_page():
    """
    Placeholder for another function/page.
    """
    st.title("📊 Logistics Dashboard (Placeholder)")
    st.markdown("This section will eventually show visualizations or metrics related to your logistics data.")
    st.image("https://placehold.co/800x400/94A3B8/FFFFFF?text=Data+Visualization+Here", caption="A placeholder chart") 
    st.write("Current companies count: [Fetch count from Supabase here]")

# --- Main App Execution ---

# 1. Set Page Configuration
st.set_page_config(
    page_title="Supabase Logistics App",
    layout="wide",
    initial_sidebar_state="auto",
)

# 2. Initialize Session State for Navigation
if "page" not in st.session_state:
    st.session_state.page = "Home"

# 3. Sidebar (for returning home)
st.sidebar.title("Navigation")
if st.session_state.page != "Home":
    if st.sidebar.button("🏠 Back to Home", key="home_btn"):
        navigate_to("Home")
else:
    # Give a brief context on the home page
    st.sidebar.markdown("Use the buttons below to switch features.")


# 4. Conditional Page Rendering
if st.session_state.page == "Home":
    show_home_page()
elif st.session_state.page == "Add Supplier":
    show_data_uploader_page(supabase)
elif st.session_state.page == "Dashboard":
    show_dashboard_page()
