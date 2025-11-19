import streamlit as st
import pandas as pd
import os
import sys

# --- FIX: Add the project root directory to the Python path ---
# This line is kept to ensure this page can easily be expanded later 
# if it needs to import modules from the root.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# ---------------------------------------------------------------

# --- Page Title and Introduction ---
st.title("📦 Add Supplier Data (Step 1: File Input)")
st.markdown("Upload your supplier data file below to preview the contents.")

# =========================================================================
# STEP 1: Display Input Field, Handle Upload, and Show DataFrame
# =========================================================================
st.subheader("1. Upload File and Select Company Column")

# 1. File Uploader Widget (The drag-and-drop element)
uploaded_file = st.file_uploader(
    "Drag and drop your Excel (.xlsx) or CSV (.csv) file here", 
    type=["xlsx", "csv"],
    help="The file must contain a column with the company/supplier names."
)

if uploaded_file is None:
    st.info("Awaiting file upload...")
    # Stop execution if no file is present
    st.stop() 

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
        options=column_options,
        # Set a default value if the word "name" exists in any column header
        index=next((i for i, col in enumerate(column_options) if 'name' in col.lower()), 0)
    )
    
    if company_column:
        st.success(f"Selected supplier column: **{company_column}**")
    
except Exception as e:
    st.error(f"An error occurred while reading or processing the file. Error: {e}")
    st.stop()
