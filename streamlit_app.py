import streamlit as st

# 设置页面配置
st.set_page_config(
    page_title="货运检查主页",
    page_icon="📦",
    layout="centered"
)

# 页面标题
st.title("📦 欢迎使用货运检查系统")

# 简要说明
st.markdown("请选择一个检查工具：")

# 使用 sidebar 导航
with st.sidebar:
    st.header("导航")
    st.page_link("pages/burnard_shipment_check.py", label="🚚 Burnard Shipment Check")
    st.page_link("pages/dhl_shipment_check.py", label="✈️ DHL Shipment Check")

# 主页面内容
st.image("https://cdn-icons-png.flaticon.com/512/104/104512.png", width=100)
st.markdown("""
这是一个用于检查货运状态的工具主页。  
请使用左侧导航栏选择您要运行的检查程序。
""")
