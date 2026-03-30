import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import time, datetime, timedelta
import os
from openai import OpenAI
import json
import hashlib

# -------------------------- 登录注册系统（完整整合） --------------------------
def encrypt_password(password):
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def init_user_db():
    if not os.path.exists("user_data"):
        os.mkdir("user_data")
    if not os.path.exists("user_data/users.json"):
        with open("user_data/users.json", "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def register_user(username, password):
    init_user_db()
    with open("user_data/users.json", "r", encoding="utf-8") as f:
        users = json.load(f)
    if username in users:
        return False, "用户名已存在！"
    users[username] = {"password": encrypt_password(password)}
    with open("user_data/users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    return True, "注册成功！"

def login_user(username, password):
    init_user_db()
    try:
        with open("user_data/users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
        if username not in users:
            return False, "用户名不存在！"
        if users[username]["password"] != encrypt_password(password):
            return False, "密码错误！"
        return True, "登录成功！"
    except Exception as e:
        return False, f"登录异常：{str(e)}"

def reset_password(username, new_password):
    init_user_db()
    with open("user_data/users.json", "r", encoding="utf-8") as f:
        users = json.load(f)
    if username not in users:
        return False, "用户名不存在！"
    users[username]["password"] = encrypt_password(new_password)
    with open("user_data/users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    return True, "密码重置成功！"

# 初始化登录状态
if "is_login" not in st.session_state:
    st.session_state.is_login = False
if "current_user" not in st.session_state:
    st.session_state.current_user = ""

# -------------------------- AI睡眠分析函数 --------------------------
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

# -------------------------- 网页布局 --------------------------
st.set_page_config(page_title="睡眠记录分析", layout="wide")

# -------------------------- 未登录界面 --------------------------
if not st.session_state.is_login:
    st.title("😴 睡眠记录分析 - 用户中心")
    tab1, tab2, tab3 = st.tabs(["登录", "注册", "忘记密码"])

    with tab1:
        st.subheader("用户登录")
        login_username = st.text_input("用户名", placeholder="请输入用户名", key="login_user")
        login_password = st.text_input("密码", placeholder="请输入密码", type="password", key="login_pwd")
        if st.button("登录", type="primary", use_container_width=True):
            if not login_username or not login_password:
                st.warning("请输入用户名和密码！")
            else:
                success, msg = login_user(login_username, login_password)
                if success:
                    st.session_state.is_login = True
                    st.session_state.current_user = login_username
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with tab2:
        st.subheader("用户注册")
        reg_username = st.text_input("用户名", placeholder="设置用户名", key="reg_user")
        reg_password = st.text_input("密码", placeholder="设置密码", type="password", key="reg_pwd")
        reg_confirm = st.text_input("确认密码", placeholder="再次输入密码", type="password", key="reg_confirm")
        if st.button("注册", use_container_width=True):
            if not reg_username or not reg_password:
                st.warning("用户名和密码不能为空！")
            elif reg_password != reg_confirm:
                st.warning("两次密码不一致！")
            else:
                success, msg = register_user(reg_username, reg_password)
                if success:
                    st.success(msg)
                    st.info("注册成功！请前往登录页面登录")
                else:
                    st.error(msg)

    with tab3:
        st.subheader("重置密码")
        reset_user = st.text_input("用户名", placeholder="请输入用户名", key="reset_user")
        new_pwd = st.text_input("新密码", placeholder="请输入新密码", type="password", key="new_pwd")
        confirm_pwd = st.text_input("确认新密码", placeholder="再次确认新密码", type="password", key="confirm_pwd")
        if st.button("重置密码", type="primary", use_container_width=True):
            if not reset_user or not new_pwd or not confirm_pwd:
                st.warning("所有项都不能为空！")
            elif new_pwd != confirm_pwd:
                st.warning("两次新密码不一致！")
            else:
                success, msg = reset_password(reset_user, new_pwd)
                if success:
                    st.success(msg)
                    st.info("请返回登录页登录")
                else:
                    st.error(msg)
    st.stop()

# -------------------------- 已登录主程序 --------------------------
st.title(f"😴 睡眠记录分析小工具 — 欢迎 {st.session_state.current_user}")

# 退出登录
with st.sidebar:
    if st.button("🚪 退出登录", use_container_width=True, type="secondary"):
        st.session_state.is_login = False
        st.session_state.current_user = ""
        if "sleep_data" in st.session_state:
            del st.session_state.sleep_data
        st.rerun()

# 创建用户专属睡眠数据
user_file = f"user_data/{st.session_state.current_user}_sleep.json"
if "sleep_data" not in st.session_state:
    if os.path.exists(user_file):
        with open(user_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        st.session_state.sleep_data = pd.DataFrame(data)
    else:
        st.session_state.sleep_data = pd.DataFrame(
            columns=["日期", "入睡时间", "起床时间", "睡眠时长(小时)", "睡眠评分", "分析结论"]
        )

# 保存用户数据到文件
def save_user_sleep_data():
    df = st.session_state.sleep_data
    with open(user_file, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

# 添加睡眠记录
with st.sidebar:
    st.divider()
    st.header("添加今日睡眠")
    date = st.date_input("日期")
    sleep_time = st.time_input("入睡时间", time(23, 30))
    getup_time = st.time_input("起床时间", time(7, 30))
    save_clicked = st.button("💾 保存记录")

# 保存逻辑
if save_clicked:
    date_str = str(date).strip()
    df = st.session_state.sleep_data
    if not df.empty and date_str in df["日期"].values:
        st.error(f"❌ 日期 {date_str} 已存在记录！")
    elif sleep_time == getup_time:
        st.error("❌ 入睡和起床时间不能相同！")
    else:
        def get_hour(t): return t.hour + t.minute / 60
        sleep_h = get_hour(sleep_time)
        getup_h = get_hour(getup_time)
        duration = getup_h - sleep_h if getup_h > sleep_h else (getup_h + 24) - sleep_h
        duration = round(duration, 2)

        if duration < 1:
            st.error(f"❌ 睡眠时间过短：{duration}小时")
        else:
            score = 0
            if 7 <= duration <= 9: score += 45
            elif 6 <= duration <7: score +=30
            elif 5<=duration<6: score +=15
            elif 4<=duration<5: score +=5

            sleep_h_val = sleep_time.hour + sleep_time.minute/60
            if 22<=sleep_h_val<=23: score +=35
            elif 23<sleep_h_val<=23.5: score +=25
            elif 23.5<sleep_h_val<=24: score +=15
            elif 0<=sleep_h_val<=1: score +=5
            score +=20

            if score>=85: conclusion="睡眠优秀"
            elif score>=70: conclusion="睡眠良好"
            elif score>=50: conclusion="睡眠一般，建议调整"
            elif score>=30: conclusion="睡眠较差，熬夜/不足"
            else: conclusion="睡眠极差，严重影响健康"

            new_row = {
                "日期": date_str,
                "入睡时间": sleep_time.strftime("%H:%M"),
                "起床时间": getup_time.strftime("%H:%M"),
                "睡眠时长(小时)": duration,
                "睡眠评分": score,
                "分析结论": conclusion
            }
            df_new = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df_new = df_new.sort_values("日期").reset_index(drop=True)
            st.session_state.sleep_data = df_new
            save_user_sleep_data()
            st.success("✅ 保存成功！")

df = st.session_state.sleep_data

# TAB切换
if "tab" not in st.session_state:
    st.session_state.tab = "记录"
tab_choice = st.radio("", ["睡眠记录", "睡眠分析", "💡睡眠建议"], horizontal=True, key="tab")

# 睡眠记录
if tab_choice == "睡眠记录":
    st.subheader("历史记录")
    if "show_del_date" not in st.session_state: st.session_state.show_del_date=False
    if "show_clear_all" not in st.session_state: st.session_state.show_clear_all=False

    if not df.empty:
        st.dataframe(df, use_container_width=True)
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ 删除单天记录", use_container_width=True, disabled=st.session_state.show_clear_all):
                st.session_state.show_del_date=True
                st.session_state.show_clear_all=False
        with col2:
            if st.button("🗑️ 清空全部记录", use_container_width=True, disabled=st.session_state.show_del_date):
                st.session_state.show_clear_all=True
                st.session_state.show_del_date=False

        if st.session_state.show_del_date:
            del_date = st.selectbox("选择日期", df["日期"].unique())
            c1,c2=st.columns(2)
            with c1:
                if st.button("✅ 确认删除", use_container_width=True):
                    df_new = df[df["日期"]!=del_date].reset_index(drop=True)
                    st.session_state.sleep_data=df_new
                    save_user_sleep_data()
                    st.success(f"已删除 {del_date}")
                    st.session_state.show_del_date=False
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.show_del_date=False
                    st.rerun()

        if st.session_state.show_clear_all:
            st.warning("⚠️ 确定清空所有记录？不可恢复！")
            c1,c2=st.columns(2)
            with c1:
                if st.button("✅ 确认清空", use_container_width=True):
                    st.session_state.sleep_data = pd.DataFrame(columns=df.columns)
                    save_user_sleep_data()
                    st.success("已清空")
                    st.session_state.show_clear_all=False
                    st.rerun()
            with c2:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.show_clear_all=False
                    st.rerun()
    else:
        st.info("请先添加睡眠记录～")

# 睡眠分析
elif tab_choice == "睡眠分析":
    st.subheader("睡眠情况智能分析")
    if not df.empty:
        df["入睡小时"] = df["入睡时间"].apply(lambda x: int(x.split(":")[0]) + int(x.split(":")[1])/60)
        col1,col2,col3=st.columns(3)
        with col1: st.metric("平均睡眠时长", f"{round(df['睡眠时长(小时)'].mean(),2)}h")
        with col2: st.metric("平均睡眠评分", f"{round(df['睡眠评分'].mean(),1)}分")
        with col3: st.metric("熬夜次数", len(df[(df["入睡时间"]>"23:50") | (df["入睡时间"]<"06:00")]))
        col4,col5,col6=st.columns(3)
        with col4: st.metric("总记录天数", len(df))
        with col5: st.metric("最高评分", f"{df['睡眠评分'].max()}分")
        with col6: st.metric("最低评分", f"{df['睡眠评分'].min()}分")

        st.markdown("---")
        fig = plt.figure(figsize=(18,10))
        df_plot=df.dropna().copy()

        # 图1：每日睡眠时长
        ax1 = plt.subplot(2, 2, 1)
        colors = []
        for h in df_plot["睡眠时长(小时)"]:
            if h < 5:
                colors.append("#ff4d4f")
            elif h < 7:
                colors.append("#ffa940")
            elif h <= 9:
                colors.append("#52c41a")
            else:
                colors.append("#1890ff")

        ax1.bar(df_plot["日期"], df_plot["睡眠时长(小时)"], color=colors, alpha=0.85, edgecolor='white', linewidth=1.5)
        ax1.axhline(7, color='#ff4d4f', linestyle='--', linewidth=2, label='At least 7 hours')
        ax1.set_title("Daily Sleep Duration", fontsize=14, pad=15)
        ax1.set_ylabel("hours")
        ax1.tick_params(axis='x', rotation=45)
        ax1.grid(alpha=0.2)
        ax1.legend(loc='upper right')

        # 图2：入睡时间节律
        ax2 = plt.subplot(2, 2, 2)
        ax2.plot(df_plot["日期"], df_plot["入睡小时"], marker='o', color='#722ed1',
                 linewidth=2, markersize=8, markerfacecolor='white', markeredgewidth=2)
        ax2.axhline(23 + 50 / 60, color='#ff4d4f', linestyle='--', linewidth=2, label='warning line 23:50')
        ax2.set_title("Sleep Time", fontsize=14, pad=15)
        ax2.set_ylabel("24h")
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(alpha=0.2)
        ax2.legend(loc='upper right')

        # 图3：睡眠评分趋势
        ax3 = plt.subplot(2, 1, 2)
        ax3.plot(df_plot["日期"], df_plot["睡眠评分"], color='#13c2c2', linewidth=3, marker='o', markersize=9)
        ax3.axhline(70, color='orange', linestyle='--', linewidth=2, label='Passing line 70')
        ax3.set_title("Sleep Quality Score Trend", fontsize=14, pad=15)
        ax3.set_ylabel("score")
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(alpha=0.2)
        ax3.legend(loc='upper right')

        plt.tight_layout()
        st.pyplot(fig)

        st.markdown("### 📌 睡眠规律总结")
        st.write(f"最近7天平均睡眠：**{round(df[-7:]['睡眠时长(小时)'].mean(),1)}h**")
        st.write(f"最近7天平均入睡：**{round(df[-7:]['入睡小时'].mean(),1)}点**")
        st.write(f"睡眠达标天数：**{len(df[df['睡眠评分']>=70])}天**")
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
            with st.spinner("🧠 AI正在生成睡眠报告..."):
                stream = ai_sleep_analysis_stream(dur, sleep_time_str)
            st.markdown("### 📊 AI睡眠分析报告")
            full = ""
            out = st.empty()
            for chunk in stream:
                try:
                    token = chunk.choices[0].delta.content or ""
                    full += token
                    out.markdown(full)
                except:
                    continue

# 导出
st.sidebar.markdown("---")
if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.sidebar.download_button("📥 导出睡眠数据", csv, "睡眠记录.csv", "text/csv")
