import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
import sys
# Import the custom utility functions from your existing file, including the new one
from supabase_data_updater import upload_new_companies, upload_new_ports, extract_port_codes_and_suppliers

# --- Supabase Initialization (Placeholder for Configuration) ---
# NOTE: This block is crucial.
try:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", st.secrets.get("SUPABASE_URL"))
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY"))
    
    # Initialize Supabase client
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_KEY in your secrets.")
        supabase = None
    else:
        # Use a non-global variable for the client to ensure clean setup
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Error initializing Supabase client. Error: {e}")
    # Setting supabase to None ensures the app doesn't crash but shows an error message
    supabase = None

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
        if st.button("➕ Add Supplier & Port Data", key="add_supplier_btn", help="Upload a new Excel/CSV file to update the companies and ports lists."):
            navigate_to("Add Supplier")

    with col2:
        st.info("Function 2: View Metrics")
        if st.button("📊 View Dashboard", key="view_dashboard_btn", help="See key performance indicators and visualizations."):
            navigate_to("Dashboard")

    with col3:
        st.info("Function 3: Future Feature")
        st.button("⚙️ Configuration", disabled=True, help="Coming soon...")
        
    st.markdown("---")
    # Display Supabase connection status
    if supabase:
        st.write("Current Supabase Connection Status: **Ready**")
    else:
        st.warning("Supabase Connection Status: **Not Configured** (Upload functions will fail)")

def show_data_uploader_page(supabase: Client):
    """
    Displays the UI for file upload and database update logic (The 'Add Supplier' page).
    Handles data extraction, company upload, and port upload.
    """
    st.title("📦 Data Uploader (Companies and Ports)")
    st.markdown("Upload your latest logistics report. The system will automatically identify, clean, and extract unique company names and port codes (UN/LOCODEs) before inserting them into the Supabase database.")
    
    if supabase is None:
        st.error("Cannot access this feature. Supabase client failed to initialize due to missing credentials.")
        return

    # 1. File Uploader Widget
    uploaded_file = st.file_uploader(
        "Drag and drop your Excel (.xlsx) or CSV (.csv) logistics report here", 
        type=["xlsx", "csv"],
        help="The system will try to automatically detect the header row and relevant columns based on common logistics report formats."
    )

    # 2. Main Processing Logic
    if uploaded_file is not None:
        st.success(f"File uploaded successfully: **{uploaded_file.name}**")
        
        file_extension = uploaded_file.name.split('.')[-1].lower()

        # The primary button to kick off the process
        if st.button("Process & Upload All Data", type="primary"):
            with st.spinner("Analyzing file structure, cleaning data, and preparing for upload..."):
                
                # --- Step 1: Clean and Extract Data ---
                # The file object needs to be cloned or read fully because pandas and manual reading 
                # might exhaust the file buffer. Simple file.seek(0) should usually suffice 
                # if the file isn't massive, but we trust the inner function to handle seek(0).
                extraction_result = extract_port_codes_and_suppliers(uploaded_file, file_extension)

                if not extraction_result['success']:
                    st.error(f"❌ Extraction Failed: {extraction_result['message']}")
                    return

                unique_suppliers = extraction_result['unique_suppliers']
                unique_port_codes = extraction_result['unique_port_codes']
                
                st.info(extraction_result['message'])
                st.subheader("Extracted Data Summary")
                st.write(f"Found **{len(unique_suppliers)}** unique supplier names.")
                st.write(f"Found **{len(unique_port_codes)}** unique 5-letter UN/LOCODEs.")

            
            # --- Step 2: Upload Companies ---
            with st.spinner("Uploading unique companies to the 'companies' table..."):
                company_result = upload_new_companies(supabase, unique_suppliers)
            
            if company_result['success']:
                st.success(f"Company Upload Status: {company_result['message']}")
            else:
                st.error(f"Company Upload Failed: {company_result['message']}")


            # --- Step 3: Upload Ports ---
            with st.spinner("Uploading new port codes to the 'ports' table (linking to countries)..."):
                port_result = upload_new_ports(supabase, unique_port_codes)

            if port_result['success']:
                st.success(f"Port Upload Status: {port_result['message']}")
                if port_result.get('ports_without_country'):
                    st.warning(f"⚠️ **{len(port_result['ports_without_country'])}** port codes could not be matched to a country (first 2 letters of UN/LOCODE) and were skipped.")
            else:
                st.error(f"Port Upload Failed: {port_result['message']}")
                
            st.balloons()
            st.success("🎉 All uploads complete! Check the Supabase console for details.")


    else:
        st.info("Awaiting file upload...")

def show_dashboard_page():
    """
    Placeholder for the Dashboard page.
    """
    st.title("📊 Logistics Dashboard (Placeholder)")
    st.markdown("This section will eventually show visualizations or metrics related to your logistics data.")
    st.image("https://placehold.co/800x400/94A3B8/FFFFFF?text=Data+Visualization+Here", caption="A placeholder chart") 
    # Example placeholder: This would require a fetch call to Supabase
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
