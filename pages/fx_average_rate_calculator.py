import streamlit as st
import pandas as pd

# =========================
# Page configuration
# =========================
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

# =========================
# Currency selection (display only)
# =========================
currency = st.selectbox(
    "Invoice Currency",
    ["USD - US Dollar", "AUD - Australian Dollar", "JPY - Japanese Yen", "CNY - Chinese Yuan"]
)

st.markdown("### Payment Inputs")

# =========================
# Initialize session state
# =========================
DEFAULT_ROWS = 3

if "fx_rows" not in st.session_state:
    st.session_state.fx_rows = DEFAULT_ROWS

# =========================
# Control buttons
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("➕ Add Row"):
        st.session_state.fx_rows += 1

with col2:
    if st.session_state.fx_rows > 1:
        if st.button("➖ Remove Row"):
            st.session_state.fx_rows -= 1

with col3:
    if st.button("♻️ Clear / Reset"):
        # reset rows
        st.session_state.fx_rows = DEFAULT_ROWS

        # reset all inputs
        for key in list(st.session_state.keys()):
            if key.startswith("fx_pay_") or key.startswith("fx_rate_"):
                del st.session_state[key]

        st.experimental_rerun()

data = []

# =========================
# Input rows
# =========================
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

