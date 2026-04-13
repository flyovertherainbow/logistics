import streamlit as st
import pandas as pd

# =========================
# 页面配置（决定 side menu 显示名称和图标）
# =========================
st.set_page_config(
    page_title="FX Average Rate Calculator",
    page_icon="💱",
    layout="centered"
)

st.title("💱 外汇平均汇率计算器")
st.caption("用于多次按不同汇率支付外币，自动计算加权平均汇率（NZD / 外币）")

st.markdown("---")

# =========================
# 币种选择（仅做展示）
# =========================
currency = st.selectbox(
    "货款币种",
    ["USD - 美元", "AUD - 澳币", "JPY - 日元", "CNY - 人民币"]
)

st.markdown("### 输入每次付款信息")

# =========================
# 动态行数（使用 session_state）
# =========================
if "fx_rows" not in st.session_state:
    st.session_state.fx_rows = 3

col1, col2 = st.columns(2)

with col1:
    if st.button("➕ 添加一行"):
        st.session_state.fx_rows += 1

with col2:
    if st.session_state.fx_rows > 1:
        if st.button("➖ 删除一行"):
            st.session_state.fx_rows -= 1

data = []

for i in range(st.session_state.fx_rows):
    st.markdown(f"**付款 {i + 1}**")
    c1, c2 = st.columns(2)

    with c1:
        pay = st.number_input(
            f"外币金额 pay-{i + 1}",
            min_value=0.0,
            step=100.0,
            format="%.2f",
            key=f"fx_pay_{i}",
        )

    with c2:
        rate = st.number_input(
            f"汇率 ex-{i + 1}（NZD / 外币）",
            min_value=0.0,
            step=0.0001,
            format="%.6f",
            key=f"fx_rate_{i}",
        )

    data.append(
        {
            "外币金额": pay,
            "汇率 (NZD/外币)": rate
        }
    )

st.markdown("---")

# =========================
# 计算逻辑
# =========================
if st.button("📊 计算平均汇率"):
    df = pd.DataFrame(data)

    total_foreign = df["外币金额"].sum()
    total_nzd = (df["外币金额"] * df["汇率 (NZD/外币)"]).sum()

    if total_foreign == 0:
        st.error("❌ 外币总额为 0，无法计算平均汇率")
    else:
        avg_rate = total_nzd / total_foreign

        st.success("✅ 计算完成")

        st.markdown("### 📌 结果汇总")
        st.write(f"**币种**：{currency}")
        st.write(f"**外币总额**：{total_foreign:,.2f}")
        st.write(f"**纽币总支出（NZD）**：{total_nzd:,.2f}")
        st.markdown(f"### ⭐ 平均汇率：`{avg_rate:.6f}`  NZD / 外币")

        with st.expander("查看计算明细"):
            df["NZD 支出"] = df["外币金额"] * df["汇率 (NZD/外币)"]
            st.dataframe(df, use_container_width=True)
