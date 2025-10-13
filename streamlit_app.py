import streamlit as st

# 设置页面配置
st.set_page_config(
    page_title="IMPORT DOC UPDATER",
    page_icon="📦",
    layout="centered"
)

# 页面标题
st.title("📦 IMPORT DOC UPDATE TOOL")

# 简要说明
#st.markdown("SELECT FORWARDER FROM THE SIDE MENU")

# 使用 sidebar 导航
#with st.sidebar:
#    st.header("MENU")
#    st.page_link("pages/burnard_shipment_check.py", label="🚚 Burnard Shipment Check")
#    st.page_link("pages/dhl_shipment_check.py", label="✈️ DHL Shipment Check")

# 主页面内容
#st.image("https://cdn-icons-png.flaticon.com/512/104/104512.png", width=100)
st.markdown("""
SELECT FORWARDER FROM THE SIDE MENU
""")
