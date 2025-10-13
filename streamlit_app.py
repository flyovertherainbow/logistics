import streamlit as st

st.set_page_config(page_title="Shipment Checker", page_icon="📦")

with st.sidebar:
    st.page_link("burnard_shipment_check.py", label="Burnard Shipment Check", icon="🚚")
    st.page_link("dhl_shipment_check.py", label="DHL Shipment Check", icon="✈️")

st.title("欢迎使用货运检查系统")
st.write("请从左侧选择一个检查工具。")
