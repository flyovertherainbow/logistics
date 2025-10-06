import streamlit as st
import pandas as pd

st.title("🔍 Excel PO Comparison Tool")

file_a = st.file_uploader("Upload Excel A (with 'All references')", type=["xlsx"])
file_b = st.file_uploader("Upload Excel B (with 'BC PO')", type=["xlsx"])

if file_a and file_b:
    df_a = pd.read_excel(file_a)
    df_b = pd.read_excel(file_b)

    df_a['PO_number'] = df_a['All references'].astype(str).str.extract(r'PO(\d{6})')
    df_b['BC PO'] = df_b['BC PO'].astype(str).str.zfill(6)

    merged = pd.merge(df_a, df_b, left_on='PO_number', right_on='BC PO', how='left', indicator=True)

    not_found = merged[merged['_merge'] == 'left_only']
    st.subheader("❌ POs in A not found in B")
    st.write(not_found[['All references']])

    matched = merged[merged['_merge'] == 'both']
    st.subheader("✅ Matched POs with column differences")

    common_cols = set(df_a.columns).intersection(set(df_b.columns))
    for col in common_cols:
        col_x = col + '_x'
        col_y = col + '_y'
        if col_x in matched.columns and col_y in matched.columns:
            diffs = matched[matched[col_x] != matched[col_y]]
            if not diffs.empty:
                st.markdown(f"**Column: {col}**")
                st.dataframe(diffs[['All references', col_x, col_y]])

    st.success("Comparison complete.")
