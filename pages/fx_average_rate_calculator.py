import streamlit as st
import pandas as pd

# ==============================
# Page configuration
# ==============================
st.set_page_config(
    page_title="FX Average Rate Calculator",
    page_icon="💱",
    layout="centered"
)

st.title("💱 FX Average Rate Calculator")
st.caption(
    "Calculate the weighted average FX rate when paying a foreign currency invoice "
    "in multiple instalments using NZD."
)

st.markdown("---")

# ==============================
# Currency selection
# ==============================
currency = st.selectbox(
    "Invoice Currency",
    [
        "USD - US Dollar",
        "AUD - Australian Dollar",
        "JPY - Japanese Yen",
        "CNY - Chinese Yuan",
    ],
)

# Extract just the 3-letter code (e.g., "USD") for cleaner labels
curr_code = currency.split(" ")[0] 

st.markdown("### Payment Inputs")

# ==============================
# Session state initialization
# ==============================
DEFAULT_ROWS = 3

if "fx_rows" not in st.session_state:
    st.session_state.fx_rows = DEFAULT_ROWS

# ==============================
# Buttons
# ==============================
col1, col2, col3 = st.columns(3)

if col1.button("➕ Add Row"):
    st.session_state.fx_rows += 1

if col2.button("➖ Remove Row"):
    if st.session_state.fx_rows > 1:
        st.session_state.fx_rows -= 1

if col3.button("♻️ Clear / Reset"):
    st.session_state.fx_rows = DEFAULT_ROWS

    keys_to_delete = []
    for key in st.session_state.keys():
        if key.startswith("fx_pay_") or key.startswith("fx_rate_"):
            keys_to_delete.append(key)

    for key in keys_to_delete:
        del st.session_state[key]

    st.rerun()

# ==============================
# Input rows
# ==============================
rows_data = []

for i in range(st.session_state.fx_rows):
    st.markdown(f"**Payment {i + 1}**")

    c1, c2 = st.columns(2)

    with c1:
        pay = st.number_input(
            f"Foreign Amount (pay-{i + 1})",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key=f"fx_pay_{i}",
        )

    with c2:
        # UPDATED: Changed label from NZD / Foreign to Foreign / NZD (e.g., USD / NZD)
        rate = st.number_input(
            f"FX Rate (ex-{i + 1})  {curr_code} / NZD",
            min_value=0.0,
            step=0.0001,
            format="%.6f",
            key=f"fx_rate_{i}",
        )

    rows_data.append(
        {
            "Foreign Amount": pay,
            f"FX Rate ({curr_code}/NZD)": rate,
        }
    )

st.markdown("---")

# ==============================
# Calculation
# ==============================
if st.button("📊 Calculate Average Rate"):
    df = pd.DataFrame(rows_data)

    total_foreign = df["Foreign Amount"].sum()
    
    # UPDATED LOGIC: 
    # Since the input rate is now Foreign/NZD (e.g., how many USD per 1 NZD),
    # NZD Amount = Foreign Amount / FX Rate
    # We protect against division by zero in case a rate field is left empty.
    rate_col = f"FX Rate ({curr_code}/NZD)"
    df["NZD Amount"] = df.apply(
        lambda row: row["Foreign Amount"] / row[rate_col] if row[rate_col] > 0 else 0.0, 
        axis=1
    )
    
    total_nzd = df["NZD Amount"].sum()

    if total_foreign == 0:
        st.error(
            "Foreign amount total is zero. "
            "Average rate cannot be calculated."
        )
    elif total_nzd == 0:
        st.error(
            "Total NZD paid is zero. Please check your FX Rate inputs."
        )
    else:
        # UPDATED LOGIC: Weighted Average in Foreign / NZD format
        avg_rate_foreign_nzd = total_foreign / total_nzd

        st.success("Calculation completed successfully.")

        st.markdown("### ✅ Summary")
        st.write(f"**Invoice Currency**: {currency}")
        st.write(f"**Total Foreign Amount**: {total_foreign:,.2f}")
        st.write(f"**Total NZD Paid**: {total_nzd:,.2f}")
        
        # UPDATED: Clearly states the result in the requested Foreign / NZD format
        st.markdown(
            f"### ⭐ Weighted Average FX Rate: "
            f"**`{avg_rate_foreign_nzd:.6f}` {curr_code} / NZD**"
        )

        with st.expander("View Calculation Details"):
            st.dataframe(df, use_container_width=True)

