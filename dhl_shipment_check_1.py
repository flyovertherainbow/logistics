import streamlit as st
import pandas as pd
import re
from datetime import datetime
# Excel A: DHL report
# Excel B: import doc
st.title("DHL Shipment Report Updater")

st.write("""
Upload your DHL Shipment Level Report and Import Doc.
This app will:
- Clean data in DHL report (removes rows with missing or invalid Estimated Arrival).
- Extract all PO numbers (including ranges and variants) from All References in DHL report.
- Compare to BC PO numbers in import doc, showing matches and unmatched POs.
- Highlight POs that appear more than once in DHL repot.
""")

excel_a = st.file_uploader("**📦 Upload DHL Shipment Report**", type=["xlsx"])
excel_b = st.file_uploader("**📄 Upload Import Doc**", type=["xlsx"])

def extract_po_numbers(ref_str):
    if not isinstance(ref_str, str):
        return []
    numbers = set()
    # Handle ranges like PO106922-23 (-> 106922, 106923)
    for match in re.finditer(r'PO\s?(\d{6})-(\d{2})', ref_str):
        base = int(match.group(1))
        end = int(match.group(2))
        start_last_two = base % 100
        for n in range(start_last_two, end + 1):
            numbers.add(str(base - start_last_two + n))
    # Handle format: PO106236/PO106268 or PO106236 / PO106268
    for group in re.split(r'[\/,]', ref_str):
        m = re.search(r'PO[.\s]?\s?(\d{6})', group)
        if m:
            numbers.add(m.group(1))
        # Capture lone 6-digit numbers
        lone = re.findall(r'\b\d{6}\b', group)
        for num in lone:
            numbers.add(num)
    # Capture PO numbers with suffixes (e.g. PO106177-R2)
    for m in re.finditer(r'PO[.\s]?\s?(\d{6})-\w+', ref_str):
        numbers.add(m.group(1))
    return list(numbers)

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

def is_container_value(val):
    """Checks if the value matches (20GP), (40HC), (20RE), (40RE), (40GP)"""
    if isinstance(val, str):
        return bool(re.match(r"\((20GP|40HC|20RE|40RE|40GP)\)", val.strip()))
    return False

def is_same_day(date_a, date_b):
    """Checks if date_a and date_b are the same day (ignores time)."""
    try:
        d_a = pd.to_datetime(date_a)
        d_b = pd.to_datetime(date_b)
        return d_a.date() == d_b.date()
    except:
        return False

if excel_a and excel_b:
    # Read files
    df_a = pd.read_excel(excel_a)
    df_b = pd.read_excel(excel_b)

    # Clean Excel A: keep only rows with valid date in Estimated Arrival
    df_a = df_a[df_a['Estimated Arrival'].apply(is_valid_date)].copy()

    # Extract PO numbers in Excel A
    df_a['Extracted PO'] = df_a['All References'].apply(extract_po_numbers)

    # Expand rows so each PO gets its own row
    df_a_expanded = df_a.explode('Extracted PO')
    df_a_expanded = df_a_expanded[df_a_expanded['Extracted PO'].notnull()]

    # Count duplicate POs
    po_counts = df_a_expanded['Extracted PO'].value_counts()
    duplicates = po_counts[po_counts > 1]

    st.header("PO Numbers Appearing More Than Once in DHL report")
    if not duplicates.empty:
        st.write(duplicates)
    else:
        st.write("No duplicate PO numbers found in DHL report.")

    # BC PO numbers in Excel B (ensure string type)
    df_b['BC PO'] = df_b['BC PO'].astype(str)
    b_po_set = set(df_b['BC PO'])

    # Find matches and non-matches
    df_a_expanded['Match'] = df_a_expanded['Extracted PO'].apply(lambda x: x in b_po_set)

    matched = df_a_expanded[df_a_expanded['Match']]
    unmatched = df_a_expanded[~df_a_expanded['Match']]

    st.header("Matched PO Numbers")
    if not matched.empty:
        matched['BC PO'] = matched['Extracted PO']
        merged = pd.merge(matched, df_b, left_on='Extracted PO', right_on='BC PO', suffixes=('_A', '_B'))
        diff_rows = []
        compare_cols = ['Estimated Arrival', 'Container Number']  # Add more columns as needed

        for idx, row in merged.iterrows():
            diffs = {}
            for col in compare_cols:
                col_a = col + '_A'
                col_b = col + '_B'
                a_val = row.get(col_a, None)
                b_val = row.get(col_b, None)

                # 1. For Estimated Arrival: compare only date part
                if col == "Estimated Arrival":
                    if pd.isnull(a_val) and pd.isnull(b_val):
                        continue
                    if is_same_day(a_val, b_val):
                        continue
                    if a_val != b_val:
                        diffs[col] = {'Excel A': a_val, 'Excel B': b_val}
                # 2. For Container Number: Excel A NaN, Excel B is container code → not different
                elif col == "Container Number":
                    if pd.isnull(a_val) and is_container_value(b_val):
                        continue
                    if a_val != b_val:
                        diffs[col] = {'Excel A': a_val, 'Excel B': b_val}
                # 3. Default: normal compare
                else:
                    if pd.isnull(a_val) and pd.isnull(b_val):
                        continue
                    if a_val != b_val:
                        diffs[col] = {'Excel A': a_val, 'Excel B': b_val}
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

    st.header("Unmatched PO Numbers in DHL Report")
    if not unmatched.empty:
        st.write(unmatched['Extracted PO'].unique())
    else:
        st.write("All PO numbers from Excel A were found in Import Doc.")

    st.header("Downloadable Results")
    result = pd.DataFrame({
        'PO': df_a_expanded['Extracted PO'],
        'Matched': df_a_expanded['Match']
    })
    st.download_button("Download Comparison Results", result.to_csv(index=False), "comparison_results.csv", "text/csv")
else:
    st.info("Please upload both Excel files to proceed.")
