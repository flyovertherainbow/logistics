import streamlit as st
import pandas as pd
import re
from datetime import datetime

st.title("Shipment Report Comparison Tool")

st.write("""
Upload your ECLY Shipment Level Report (Excel A) and Import Doc (Excel B).
The app will compare PO numbers and show matched and unmatched results.
""")

excel_a = st.file_uploader("Upload ECLY Shipment Level Report (Excel A)", type=["xlsx"])
excel_b = st.file_uploader("Upload Import Doc (Excel B)", type=["xlsx"])

def extract_po_numbers(ref_str):
    if not isinstance(ref_str, str):
        return []
    numbers = set()
    # Handle ranges like PO106922-23
    for match in re.finditer(r'PO\s?(\d{6})-(\d{2})', ref_str):
        base = int(match.group(1))
        end = int(match.group(2))
        start_last_two = base % 100
        for n in range(start_last_two, end + 1):
            numbers.add(str(base - start_last_two + n))
    # Handle normal PO numbers: PO106918, PO 106918, PO. 106918, etc.
    for match in re.finditer(r'PO[.\s]?\s?(\d{6})', ref_str):
        numbers.add(match.group(1))
    # Also include 6-digit numbers that might not be preceded by PO
    for match in re.finditer(r'\b(\d{6})\b', ref_str):
        numbers.add(match.group(1))
    return list(numbers)


#def extract_6digit_numbers(ref_str):
    # Find all 6-digit numbers
#    if isinstance(ref_str, str):
#        return re.findall(r'\b\d{6}\b', ref_str)
#    return []

if excel_a and excel_b:
    # Read files
    df_a = pd.read_excel(excel_a)
    df_b = pd.read_excel(excel_b)

    # Clean Excel A: keep only rows with valid date in Estimated Arrival
    def is_valid_date(val):
        if pd.isnull(val):
            return False
        if isinstance(val, datetime):
            return True
        try:
            pd.to_datetime(val)
            return True
        except:
            return False

    df_a = df_a[df_a['Estimated Arrival'].apply(is_valid_date)].copy()

    # Extract all 6-digit numbers from All References in Excel A
    df_a['Extracted PO'] = df_a['All References'].apply(extract_po_numbers)

    # Flatten out rows so each PO gets its own row
    df_a_expanded = df_a.explode('Extracted PO')
    df_a_expanded = df_a_expanded[df_a_expanded['Extracted PO'].notnull()]

    # BC PO numbers in Excel B (make sure they're strings)
    df_b['BC PO'] = df_b['BC PO'].astype(str)
    b_po_set = set(df_b['BC PO'])

    # Find matches and non-matches
    df_a_expanded['Match'] = df_a_expanded['Extracted PO'].apply(lambda x: x in b_po_set)

    matched = df_a_expanded[df_a_expanded['Match']]
    unmatched = df_a_expanded[~df_a_expanded['Match']]

    st.header("Matched PO Numbers")
    if not matched.empty:
        # Compare other columns for matched PO numbers
        matched['BC PO'] = matched['Extracted PO']
        merged = pd.merge(matched, df_b, left_on='Extracted PO', right_on='BC PO', suffixes=('_A', '_B'))
        diff_rows = []
        # Compare relevant columns
        compare_cols = ['Estimated Arrival', 'Container Number']  # add more if needed
        for idx, row in merged.iterrows():
            diffs = {}
            for col in compare_cols:
                col_a = col + '_A'
                col_b = col + '_B'
                if col_a in merged.columns and col_b in merged.columns:
                    if pd.isnull(row[col_a]) and pd.isnull(row[col_b]):
                        continue
                    if row[col_a] != row[col_b]:
                        diffs[col] = {'Excel A': row[col_a], 'Excel B': row[col_b]}
            if diffs:
                diff_rows.append({'PO': row['Extracted PO'], 'Differences': diffs})
        if diff_rows:
            st.write("Rows with differences in Estimated Arrival or Container Number:")
            for row in diff_rows:
                st.write(f"PO: {row['PO']}")
                for col, diff in row['Differences'].items():
                    st.write(f" - {col}: Excel A = {diff['Excel A']}, Excel B = {diff['Excel B']}")
        else:
            st.write("No differences found in compared columns for matched POs.")
    else:
        st.write("No matched PO numbers found.")

    st.header("Unmatched PO Numbers in Excel A")
    if not unmatched.empty:
        st.write(unmatched['Extracted PO'].unique())
    else:
        st.write("All PO numbers from Excel A were found in Excel B.")

    st.header("Downloadable Results")
    # Optionally, let user download comparison results
    result = pd.DataFrame({
        'PO': df_a_expanded['Extracted PO'],
        'Matched': df_a_expanded['Match']
    })
    st.download_button("Download Comparison Results", result.to_csv(index=False), "comparison_results.csv", "text/csv")

else:
    st.info("Please upload both Excel files to proceed.")
