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
# Currency selection (display only)
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
        rate = st.number_input(
            f"FX Rate (ex-{i + 1})  NZD / Foreign",
            min_value=0.0,
            step=0.0001,
            format="%.6f",
            key=f"fx_rate_{i}",
        )

    rows_data.append(
        {
            "Foreign Amount": pay,
            "FX Rate (NZD/Foreign)": rate,
        }
    )

st.markdown("---")

# ==============================
# Calculation
# ==============================
if st.button("📊 Calculate Average Rate"):
    df = pd.DataFrame(rows_data)

    total_foreign = df["Foreign Amount"].sum()
    total_nzd = (df["Foreign Amount"] * df["FX Rate (NZD/Foreign)"]).sum()

    if total_foreign == 0:
        st.error(
            "Foreign amount total is zero. "
            "Average rate cannot be calculated."
        )
    else:
        avg_rate = total_nzd / total_foreign

        st.success("Calculation completed successfully.")

        st.markdown("### ✅ Summary")
        st.write(f"**Invoice Currency**: {currency}")
        st.write(f"**Total Foreign Amount**: {total_foreign:,.2f}")
        st.write(f"**Total NZD Paid**: {total_nzd:,.2f}")
        st.markdown(
            f"### ⭐ Weighted Average FX Rate: "
            f"**`{avg_rate:.6f}` NZD / Foreign**"
        )

        with st.expander("View Calculation Details"):
            df["NZD Amount"] = (
                df["Foreign Amount"]
                * df["FX Rate (NZD/Foreign)"]
            )
            st.dataframe(df, use_container_width=True)

