import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="BURNARD SHIPMENT CHECK LIST", layout="wide")
st.title("📦 BURNARD SHIPMENT CHECK LIST")

# File upload
file_a = st.file_uploader("Upload Excel A (Client Order Followup Status Summary Report)", type=["xlsx"], key="file_a")
file_b = st.file_uploader("Upload Excel B (Import Doc)", type=["xlsx"], key="file_b")

def detect_header_row(df, keywords):
    for i in range(min(20, len(df))):
        row = df.iloc[i].astype(str).str.strip().tolist()
        if all(keyword in row for keyword in keywords):
            return i
    return None

def extract_po_numbers(order_value):
    if pd.isna(order_value):
        return []
    return re.findall(r"\b\d{6}\b", str(order_value))

def compare_rows(row_a, row_b, columns_to_compare):
    differences = {}
    for col in columns_to_compare:
        val_a = str(row_a.get(col, "")).strip()
        val_b = str(row_b.get(col, "")).strip()
        if val_a != val_b:
            differences[col] = {"Excel A": val_a, "Excel B": val_b}
    return differences

if file_a and file_b:
    df_a_raw = pd.read_excel(file_a, sheet_name=0, header=None, engine="openpyxl")
    df_b = pd.read_excel(file_b, sheet_name=0, engine="openpyxl")

    header_keywords = ["Order #", "Supplier"]
    header_row_index = detect_header_row(df_a_raw, header_keywords)

    if header_row_index is None:
        st.error("Could not detect header row in Excel A.")
    else:
        df_a = pd.read_excel(file_a, sheet_name=0, header=header_row_index, engine="openpyxl")

        # Clean Excel A: remove rows with invalid ETA
        df_a["ETA"] = pd.to_datetime(df_a["ETA"], errors="coerce")
        df_a_clean = df_a.dropna(subset=["ETA"])

        # Extract PO numbers from Excel A
        po_map_a = {}
        for idx, row in df_a_clean.iterrows():
            po_list = extract_po_numbers(row["Order #"])
            for po in po_list:
                po_map_a[po] = row

        # Extract PO numbers from Excel B
        po_set_b = set()
        for val in df_b["BC PO"]:
            po_set_b.update(extract_po_numbers(val))

        matched_differences = []
        unmatched_pos = []

        columns_to_compare = ["ETA", "Container", "Arrival Vessel", "Arrival Voyage"]

        for po, row_a in po_map_a.items():
            if po in po_set_b:
                match_rows_b = df_b[df_b["BC PO"].astype(str).str.contains(po)]
                if not match_rows_b.empty:
                    row_b = match_rows_b.iloc[0]
                    differences = compare_rows(row_a, row_b, columns_to_compare)
                    if differences:
                        matched_differences.append({"PO": po, "Differences": differences})
            else:
                unmatched_pos.append(po)

        # Display results
        st.subheader("🔍 Matched PO Differences")
        if matched_differences:
            for item in matched_differences:
                st.write(f"**PO:** {item['PO']}")
                for col, diff in item["Differences"].items():
                    st.write(f"- {col}: Excel A = `{diff['Excel A']}`, Excel B = `{diff['Excel B']}`")
        else:
            st.write("No differences found in matched POs.")

        st.subheader("❌ Unmatched PO Numbers from Excel A")
        if unmatched_pos:
            st.write(unmatched_pos)
        else:
            st.write("All PO numbers from Excel A matched with Excel B.")

        # Export buttons
        def convert_to_csv(data, columns=None):
            output = BytesIO()
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame(data, columns=columns)
            df.to_csv(output, index=False)
            return output.getvalue()

        export_matched = []
        for item in matched_differences:
            row = {"PO": item["PO"]}
            for col, diff in item["Differences"].items():
                row[col] = f"{diff['Excel A']} | {diff['Excel B']}"
            export_matched.append(row)

        st.download_button("📥 Download Matched Differences", data=convert_to_csv(export_matched),
                           file_name="matched_differences.csv", mime="text/csv")

        st.download_button("📥 Download Unmatched PO Numbers", data=convert_to_csv(unmatched_pos, columns=["Unmatched PO"]),
                           file_name="unmatched_po.csv", mime="text/csv")
