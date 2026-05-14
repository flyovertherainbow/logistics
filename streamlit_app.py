import streamlit as st

#-------
st.set_page_config(page_title="under Maintain")

hide_sidebar = """
<style>
[data-testid="stSidebar"] {display: none !important;}
</style>
"""
st.markdown(hide_sidebar, unsafe_allow_html=True)

st.warning("### 503 Service Unavailable")
st.error("Due to a GitHub Actions development configuration update, this service is currently unavailable.")
st.info("Estimated recovery time: TBD. Please try again later.")
st.stop()

#-----
# 设置页面配置
#st.set_page_config(
#    page_title="IMPORT DOC UPDATER",
#    page_icon="📦",
#    layout="centered"
#)

# 页面标题
#st.title("📦 IMPORT DOC UPDATE TOOL")

# 主页面内容

#st.markdown("""
#SELECT FORWARDER FROM THE SIDE MENU
#""")
