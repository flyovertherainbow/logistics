import streamlit as st
import pandas as pd
from supabase import create_client
from fuzzywuzzy import fuzz

# --- Configuration ---
SUPABASE_TABLE = 'suppliers'
FUZZY_MATCH_THRESHOLD = 85 # Similarity percentage (0-100)
# Configure this in .streamlit/secrets.toml
# supabase_url = "YOUR_SUPABASE_URL"
# supabase_key = "YOUR_SUPABASE_ANON_KEY"

@st.cache_resource
def init_connection():
    """Initializes the Supabase client."""
    try:
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
        return create_client(url, key)
    except Exception as e:
        st.error("🚨 Configuration Error: Supabase credentials not found in secrets.toml.")
        return None

supabase = init_connection()

@st.cache_data(show_spinner="Fetching existing suppliers...")
def fetch_existing_suppliers():
    """Fetches all existing supplier names from Supabase."""
    if not supabase: return []
    try:
        # Fetch only the supplier_name column
        response = supabase.table(SUPABASE_TABLE).select("supplier_name").execute()
        return {d['supplier_name'].upper(): d['supplier_name'] for d in response.data}
    except Exception as e:
        st.error(f"❌ Database Error: Could not fetch existing suppliers. Check table name: {e}")
        return {}

def find_fuzzy_match(new_supplier_name, existing_supplier_map, threshold):
    """Checks for exact and fuzzy matches."""
    new_supplier_upper = new_supplier_name.upper()
    
    for existing_upper, existing_original in existing_supplier_map.items():
        # 1. Check for EXACT match (case-insensitive)
        if new_supplier_upper == existing_upper:
            return existing_original, 100 # Exact match, score 100
        
        # 2. Check for FUZZY match
        similarity = fuzz.token_sort_ratio(new_supplier_upper, existing_upper)
        if similarity >= threshold:
            return existing_original, similarity
            
    return None, 0

# --- Main Streamlit App ---

st.title("Excel to Supabase Supplier Uploader")
st.markdown(f"**Similarity Threshold:** {FUZZY_MATCH_THRESHOLD}%")

if supabase is None:
    st.stop()

uploaded_file = st.file_uploader(
    "Drag and drop your Excel file here (.xlsx or .xls)",
    type=["xlsx", "xls"]
)

if uploaded_file is not None:
    st.success("File uploaded successfully! Analyzing data...")

    try:
        df = pd.read_excel(uploaded_file)
        
        if 'Supplier' not in df.columns:
            st.error("❌ Error: The file must contain a column named **'Supplier'**.")
            st.stop()
        
        # Clean and get unique list from the uploaded file
        suppliers_series = df['Supplier'].dropna().astype(str).str.strip()
        unique_suppliers_from_file = suppliers_series.unique().tolist()
        
        # Fetch current list from Supabase
        existing_supplier_map = fetch_existing_suppliers() # Map of {UPPERCASE: Original Name}

        # Lists for separation
        suppliers_to_insert = []
        fuzzy_matches_found = []

        # 1. Iterate and Check for Matches
        for new_supplier in unique_suppliers_from_file:
            
            # Find any close or exact match in the database
            matched_name, score = find_fuzzy_match(new_supplier, existing_supplier_map, FUZZY_MATCH_THRESHOLD)

            if matched_name:
                # If a match is found (exact or fuzzy), record it as a potential duplicate
                match_type = "Exact Match (Case Insensitive)" if score == 100 else "Fuzzy Match"
                fuzzy_matches_found.append({
                    "Status": match_type,
                    "New Name from File": new_supplier,
                    "Matched DB Name": matched_name,
                    "Similarity Score": f"{score}%"
                })
            else:
                # If no close match is found, prepare it for insertion
                suppliers_to_insert.append({"supplier_name": new_supplier})

        st.subheader("Data Analysis Results")
        
        # 2. Display Warnings for Potential Duplicates
        if fuzzy_matches_found:
            st.warning(f"⚠️ **{len(fuzzy_matches_found)} entries skipped** due to similarity or exact match:")
            st.dataframe(pd.DataFrame(fuzzy_matches_found), use_container_width=True)
            st.info("These suppliers were **NOT** inserted. Please standardize the names and re-upload if necessary.")
        
        # 3. Handle Insertion of Truly New Suppliers
        if suppliers_to_insert:
            st.success(f"✅ **{len(suppliers_to_insert)} truly unique suppliers** ready for insertion.")
            
            if st.button(f"Insert {len(suppliers_to_insert)} New Suppliers into Supabase"):
                
                try:
                    # Insertion logic uses ON CONFLICT for final safety check against concurrent inserts
                    response = supabase.table(SUPABASE_TABLE).insert(suppliers_to_insert).on_conflict('supplier_name').execute()
                    
                    st.balloons()
                    st.success(f"Successfully inserted {len(response.data)} new records.")

                except Exception as db_err:
                    st.error(f"❌ Database Insertion Error: {db_err}")
        else:
            if not fuzzy_matches_found:
                 st.info("No new suppliers found in the file.")
            st.stop() # Stop if there is nothing to insert.

    except Exception as e:
        st.error(f"❌ An unexpected error occurred during file processing: {e}")
        st.caption("Ensure your file is a valid Excel format and the 'Supplier' column is present.")
