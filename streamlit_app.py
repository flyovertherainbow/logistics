import streamlit as st

# 设置页面标题
st.set_page_config(page_title="Shipment Check Main Page")

# 页面标题
st.title("SHIPMENT CHECK PAGE")

# 简要说明
st.write("select forwarder：")

# 创建两个按钮链接到不同的应用
col1, col2 = st.columns(2)

with col1:
    if st.button("Burnard Shipment Check"):
        st.markdown("[ Burnard Shipment Check", unsafe_allow_html=True)

with col2:
    if st.button("DHL Shipment Check"):
        st.markdown("[ DHL Shipment Check", unsafe_allow_html=True)
