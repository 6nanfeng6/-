import streamlit as st
import pandas as pd
from datetime import time
import os
from openai import OpenAI

# AI睡眠分析函数
def ai_sleep_analysis_stream(duration, sleep_time):
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )

    prompt = f"""
    你是专业睡眠健康助手，根据数据给出专业、简洁、可执行的分析。
    睡眠时长：{duration}小时
    入睡时间：{sleep_time}

    输出：
    1.睡眠评价
    2.健康风险
    3.专业建议
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        temperature=0.3,
    )
    return response

# 网页布局
st.set_page_config(page_title="睡眠记录分析", layout="wide")
st.title("😴 睡眠记录分析小工具")

# 创建一个空表格，用来存睡眠记录
if "sleep_data" not in st.session_state:
    st.session_state.sleep_data = pd.DataFrame(
        columns=["日期", "入睡时间", "起床时间", "睡眠时长(小时)", "睡眠评分", "分析结论"]
    )

# 添加睡眠记录
with st.sidebar:
    st.header("添加今日睡眠")
    date = st.date_input("日期")
    sleep_time = st.time_input("入睡时间", time(23, 30))
    getup_time = st.time_input("起床时间", time(7, 30))

    save_clicked = st.button("💾 保存记录")

# 保存睡眠记录
if save_clicked:
    date_str = str(date).strip()
    df = st.session_state.sleep_data

    if not df.empty and date_str in df["日期"].values:
        st.error(f"❌ 日期 {date_str} 已存在睡眠记录，无法重复保存！")

    elif sleep_time == getup_time:
        st.error("❌ 入睡时间和起床时间不能相同，请重新选择！")

    else:
        def get_hour(t):
            return t.hour + t.minute / 60

        sleep_h = get_hour(sleep_time)
        getup_h = get_hour(getup_time)

        if getup_h > sleep_h:
            duration = getup_h - sleep_h
        else:
            duration = (getup_h + 24) - sleep_h
        duration = round(duration, 2)

        if duration < 1:
            st.error(f"❌ 睡眠时间过短（{duration}小时），请检查时间是否正确！")
        else:
            score = 0

            # 时长得分
            if 7 <= duration <= 9:
                score += 45
            elif 6 <= duration < 7:
                score += 30
            elif 5 <= duration < 6:
                score += 15
            elif 4 <= duration < 5:
                score += 5
            else:
                score += 0

            # 入睡时间得分
            sleep_h_val = sleep_time.hour + sleep_time.minute / 60
            if 22.0 <= sleep_h_val <= 23.0:
                score += 35
            elif 23.0 < sleep_h_val <= 23.5:
                score += 25
            elif 23.5 < sleep_h_val <= 24.0:
                score += 15
            elif 0.0 <= sleep_h_val <= 1.0:
                score += 5
            else:
                score += 0

            score += 20

            if score >= 85:
                conclusion = "睡眠优秀"
            elif score >= 70:
                conclusion = "睡眠良好"
            elif score >= 50:
                conclusion = "睡眠一般，建议调整"
            elif score >= 30:
                conclusion = "睡眠较差，熬夜/时长不足"
            else:
                conclusion = "睡眠极差，严重影响健康"

            new_row = {
                "日期": date_str,
                "入睡时间": sleep_time.strftime("%H:%M"),
                "起床时间": getup_time.strftime("%H:%M"),
                "睡眠时长(小时)": duration,
                "睡眠评分": score,
                "分析结论": conclusion
            }
            df_new = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df_new = df_new.sort_values(by="日期", ascending=True).reset_index(drop=True)

            st.session_state.sleep_data = df_new
            st.success(f"✅ 保存成功！")

df = st.session_state.sleep_data

# 固定TAB
if "tab" not in st.session_state:
    st.session_state.tab = "记录"

tab_choice = st.radio("", ["睡眠记录", "睡眠分析", "💡睡眠建议"], horizontal=True, key="tab")

# 睡眠记录
if tab_choice == "睡眠记录":
    st.subheader("历史记录")

    if "show_del_date" not in st.session_state:
        st.session_state.show_del_date = False
    if "show_clear_all" not in st.session_state:
        st.session_state.show_clear_all = False

    if not df.empty:
        st.dataframe(df)
        st.markdown("---")

        col1, col2 = st.columns(2)
        deleting = st.session_state.show_del_date
        clearing = st.session_state.show_clear_all

        with col1:
            if st.button("🗑️ 删除单天记录", use_container_width=True, disabled=clearing):
                st.session_state.show_del_date = True
                st.session_state.show_clear_all = False

        with col2:
            if st.button("🗑️ 清空全部记录", use_container_width=True, disabled=deleting):
                st.session_state.show_clear_all = True
                st.session_state.show_del_date = False

        if st.session_state.show_del_date:
            del_date = st.selectbox("选择要删除的日期", df["日期"].unique())
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 确认删除", use_container_width=True):
                    df_new = df[df["日期"] != del_date].reset_index(drop=True)
                    st.session_state.sleep_data = df_new
                    st.success(f"已删除 {del_date}")
                    st.session_state.show_del_date = False
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.show_del_date = False
                    st.rerun()

        if st.session_state.show_clear_all:
            st.warning("⚠️ 确定要清空所有记录吗？不可恢复！")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 确认清空", use_container_width=True):
                    st.session_state.sleep_data = pd.DataFrame(columns=[
                        "日期", "入睡时间", "起床时间", "睡眠时长(小时)", "睡眠评分", "分析结论"
                    ])
                    st.success("已清空所有记录")
                    st.session_state.show_clear_all = False
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.show_clear_all = False
                    st.rerun()

    else:
        st.info("请先添加睡眠记录～")

# 睡眠分析 —— 完全改用 Streamlit 原生图表，中文永不乱码
elif tab_choice == "睡眠分析":
    st.subheader("睡眠情况智能分析")

    if not df.empty:
        # 计算入睡小时
        df["入睡小时"] = df["入睡时间"].apply(lambda x: int(x.split(":")[0]) + int(x.split(":")[1])/60)

        col1, col2, col3 = st.columns(3)
        with col1:
            avg_dur = round(df["睡眠时长(小时)"].mean(), 2)
            st.metric("平均睡眠时长", f"{avg_dur} h")
        with col2:
            avg_score = round(df["睡眠评分"].mean(), 1)
            st.metric("平均睡眠评分", f"{avg_score} 分")
        with col3:
            late = len(df[(df["入睡时间"] > "23:50") | (df["入睡时间"] < "06:00")])
            st.metric("熬夜次数", late)

        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric("总记录天数", len(df))
        with col5:
            best = df["睡眠评分"].max()
            st.metric("最高评分", f"{best} 分")
        with col6:
            worst = df["睡眠评分"].min()
            st.metric("最低评分", f"{worst} 分")

        st.markdown("---")

        # 准备绘图数据
        df_chart = df[["日期", "睡眠时长(小时)", "睡眠评分", "入睡小时"]].set_index("日期")

        st.subheader("📉 每日睡眠时长")
        st.bar_chart(df_chart["睡眠时长(小时)"])

        st.subheader("📈 睡眠评分趋势")
        st.line_chart(df_chart["睡眠评分"])

        st.subheader("🌙 入睡时间节律")
        st.line_chart(df_chart["入睡小时"])

        # 总结
        st.markdown("### 📌 睡眠规律总结")
        st.write(f"✅ 最近7天平均睡眠：**{round(df[-7:]['睡眠时长(小时)'].mean(),1)}h**")
        st.write(f"✅ 最近7天平均入睡：**{round(df[-7:]['入睡小时'].mean(),1)} 点**")
        st.write(f"✅ 睡眠达标天数：**{len(df[df['睡眠评分']>=70])} 天**")

    else:
        st.info("请先添加睡眠记录")

# 睡眠建议
elif tab_choice == "💡睡眠建议":
    st.subheader("AI智能睡眠分析")
    if df.empty:
        st.info("请先添加睡眠记录")
    else:
        last = df.iloc[-1]
        dur = last["睡眠时长(小时)"]
        sleep_time_str = last["入睡时间"]

        st.markdown(f"**睡眠时长**: {dur} 小时")
        st.markdown(f"**入睡时间**: {sleep_time_str}")

        if st.button("🔍 获取AI专业分析", type="primary"):
            with st.spinner("🧠 AI正在分析睡眠报告..."):
                stream = ai_sleep_analysis_stream(dur, sleep_time_str)

            st.markdown("### 📊 AI睡眠分析报告")

            if "ai_full_text" not in st.session_state:
                st.session_state.ai_full_text = ""

            ai_output = st.empty()

            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta
                    token = delta.content if hasattr(delta, 'content') else ""
                    if token:
                        st.session_state.ai_full_text += token
                        ai_output.markdown(st.session_state.ai_full_text)
                except:
                    continue

            del st.session_state.ai_full_text

st.sidebar.markdown("---")
if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.sidebar.download_button(
        "📥 导出睡眠数据",
        csv,
        "睡眠记录.csv",
        "text/csv"
    )
