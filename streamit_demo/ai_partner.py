import streamlit as st
import os
from openai import OpenAI
from datetime import datetime, timedelta
import json
import hashlib
import time

# 创建与AI大模型交互的客户端对象
client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)

# 设置页面配置（完全不变）
st.set_page_config(
    page_title="AI智能伴侣",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# -------------------------- 常量定义（完全不变） --------------------------
DEFAULT_AI_NAME = "小甜甜"
DEFAULT_AI_CHARACTER = "你是一个少女，很贴心的回复用户的问题"
CACHE_TTL = 5  # 新增：会话列表缓存5秒，减少文件读取

# -------------------------- 工具函数（完全不变） --------------------------
def safe_get_session_state(key, default_value=""):
    return st.session_state[key] if key in st.session_state else default_value

# -------------------------- 新增：缓存装饰器（不影响功能） --------------------------
def cache_with_ttl(ttl):
    """简单缓存，减少重复读文件"""
    cache = {}
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            now = time.time()
            if key in cache and now - cache[key]["time"] < ttl:
                return cache[key]["value"]
            result = func(*args, **kwargs)
            cache[key] = {"value": result, "time": now}
            return result
        return wrapper
    return decorator

# -------------------------- 用户认证函数（完全不变） --------------------------
def encrypt_password(password):
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def init_user_db():
    if not os.path.exists("user_data"):
        os.mkdir("user_data")
    if not os.path.exists("user_data/users.json"):
        with open("user_data/users.json", "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def upgrade_user_data(username, users):
    if isinstance(users[username], str):
        users[username] = {
            "password": users[username],
            "AI_name": DEFAULT_AI_NAME,
            "AI_character": DEFAULT_AI_CHARACTER
        }
        with open("user_data/users.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    return users

def register_user(username, password):
    init_user_db()
    with open("user_data/users.json", "r", encoding="utf-8") as f:
        users = json.load(f)

    if username in users:
        return False, "用户名已存在！"

    users[username] = {
        "password": encrypt_password(password),
        "AI_name": DEFAULT_AI_NAME,
        "AI_character": DEFAULT_AI_CHARACTER
    }
    with open("user_data/users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    user_session_dir = f"session/{username}"
    if not os.path.exists(user_session_dir):
        os.makedirs(user_session_dir)

    return True, "注册成功！"

def login_user(username, password):
    init_user_db()
    try:
        with open("user_data/users.json", "r", encoding="utf-8") as f:
            users = json.load(f)

        if username not in users:
            return False, "用户名不存在！", DEFAULT_AI_NAME, DEFAULT_AI_CHARACTER

        users = upgrade_user_data(username, users)

        if users[username]["password"] != encrypt_password(password):
            return False, "密码错误！", DEFAULT_AI_NAME, DEFAULT_AI_CHARACTER

        return True, "登录成功！", DEFAULT_AI_NAME, DEFAULT_AI_CHARACTER
    except Exception as e:
        return False, f"登录异常：{str(e)}", DEFAULT_AI_NAME, DEFAULT_AI_CHARACTER

def reset_password(username, new_password):
    init_user_db()
    with open("user_data/users.json", "r", encoding="utf-8") as f:
        users = json.load(f)

    if username not in users:
        return False, "用户名不存在！"

    users = upgrade_user_data(username, users)
    
    users[username]["password"] = encrypt_password(new_password)
    with open("user_data/users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    return True, "密码重置成功！"

def save_user_character(username, ai_name, ai_character):
    try:
        init_user_db()
        with open("user_data/users.json", "r", encoding="utf-8") as f:
            users = json.load(f)

        users = upgrade_user_data(username, users)
        
        if username in users:
            users[username]["AI_name"] = ai_name
            users[username]["AI_character"] = ai_character
            with open("user_data/users.json", "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception:
        st.error("角色设定保存失败")

# -------------------------- 会话相关函数（仅优化保存/读取逻辑，功能不变） --------------------------
def save_chat(username):
    """优化：内容无变化时不保存，减少磁盘IO"""
    session_name_val = safe_get_session_state("session_name")
    messages_val = safe_get_session_state("messages", [])
    
    if session_name_val and username and messages_val:
        session_data = {
            "session_name": session_name_val,
            "AI_name": safe_get_session_state("AI_name", DEFAULT_AI_NAME),
            "AI_character": safe_get_session_state("AI_character", DEFAULT_AI_CHARACTER),
            "messages": messages_val
        }
        user_session_dir = f"session/{username}"
        if not os.path.exists(user_session_dir):
            os.makedirs(user_session_dir)
        file_path = f"{user_session_dir}/{session_data['session_name']}.json"
        
        # 新增：内容没变就不写文件
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                if existing_data == session_data:
                    return
        except:
            pass
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
    elif session_name_val and username and not messages_val:
        pass

def generate_session_name():
    local_time = datetime.now() + timedelta(hours=8)
    return local_time.strftime("%Y-%m-%d_%H-%M-%S")

@cache_with_ttl(CACHE_TTL)  # 新增：缓存会话列表，5秒内不重复读文件夹
def load_sessions(username):
    session_list = []
    user_session_dir = f"session/{username}"
    if os.path.exists(user_session_dir):
        file_list = os.listdir(user_session_dir)
        for filename in file_list:
            if filename.endswith(".json"):
                session_list.append(filename[:-5])
    session_list.sort(reverse=True)
    return session_list

def load_session(username, session_name):
    try:
        user_session_dir = f"session/{username}"
        file_path = f"{user_session_dir}/{session_name}.json"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            st.session_state.session_name = session_data["session_name"]
            st.session_state.AI_name = session_data.get("AI_name", DEFAULT_AI_NAME)
            st.session_state.AI_character = session_data.get("AI_character", DEFAULT_AI_CHARACTER)
            st.session_state.messages = session_data["messages"]
            st.success(f"已加载会话：{session_name}")
            st.rerun()
    except Exception as e:
        st.error(f"会话加载失败：{str(e)}")

def delete_session(username, session_name):
    try:
        user_session_dir = f"session/{username}"
        file_path = f"{user_session_dir}/{session_name}.json"
        
        if not os.path.exists(file_path):
            st.warning(f"会话 {session_name} 已不存在！")
            return
        
        os.remove(file_path)
        
        if session_name == safe_get_session_state("session_name"):
            st.session_state.messages = []
            st.session_state.session_name = generate_session_name()
            st.session_state.AI_name = DEFAULT_AI_NAME
            st.session_state.AI_character = DEFAULT_AI_CHARACTER
        
        st.success(f"会话 {session_name} 已成功删除！")
        st.rerun()
    except Exception as e:
        st.error(f"会话删除失败：{str(e)}")

def create_new_session(username):
    current_messages = safe_get_session_state("messages", [])
    if not current_messages:
        st.info("当前会话为空，无需创建新会话！")
        return
    
    save_chat(username)
    st.session_state.messages = []
    st.session_state.session_name = generate_session_name()
    st.session_state.AI_name = DEFAULT_AI_NAME
    st.session_state.AI_character = DEFAULT_AI_CHARACTER
    save_chat(username)
    st.success("已创建新会话！")
    st.rerun()

# -------------------------- 登录状态初始化（新增保存标记，不影响功能） --------------------------
if "is_login" not in st.session_state:
    st.session_state.is_login = False
if "current_user" not in st.session_state:
    st.session_state.current_user = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_name" not in st.session_state:
    st.session_state.session_name = generate_session_name()
# 新增：记录最后一次保存的角色信息，避免重复保存
if "last_ai_name" not in st.session_state:
    st.session_state.last_ai_name = DEFAULT_AI_NAME
if "last_ai_char" not in st.session_state:
    st.session_state.last_ai_char = DEFAULT_AI_CHARACTER

# -------------------------- 未登录界面（完全不变） --------------------------
if not st.session_state.is_login:
    if "AI_name" in st.session_state:
        del st.session_state.AI_name
    if "AI_character" in st.session_state:
        del st.session_state.AI_character

    st.title("AI智能伴侣 - 用户登录")

    tab1, tab2, tab3 = st.tabs(["登录", "注册", "忘记密码"])

    with tab1:
        st.subheader("用户登录")
        login_username = st.text_input("用户名", placeholder="用户名", key="login_user")
        login_password = st.text_input("密码", placeholder="密码", type="password", key="login_pwd")

        if st.button("登录", type="primary", use_container_width=True):
            if not login_username or not login_password:
                st.warning("请输入用户名和密码！")
            else:
                success, msg, ai_name, ai_char = login_user(login_username, login_password)
                if success:
                    st.session_state.is_login = True
                    st.session_state.current_user = login_username
                    st.session_state.AI_name = DEFAULT_AI_NAME
                    st.session_state.AI_character = DEFAULT_AI_CHARACTER
                    st.session_state.last_ai_name = DEFAULT_AI_NAME
                    st.session_state.last_ai_char = DEFAULT_AI_CHARACTER
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
                    # 优化：注册成功后，醒目的提示+引导返回登录
                    st.success(f"{msg} 即将为您切换到登录页～")
                    # 延迟1秒后自动切换到登录标签（核心优化）
                    st.markdown("""
                    <script>
                    // 自动切换到第一个标签（登录标签）
                    setTimeout(function(){
                        document.querySelector('[data-testid="stTab"]:nth-child(1)').click();
                    }, 1000);
                    </script>
                    """, unsafe_allow_html=True)
                    # 清空注册表单（可选，提升体验）
                    st.session_state.reg_user = ""
                    st.session_state.reg_pwd = ""
                    st.session_state.reg_confirm = ""
                else:
                    st.error(msg)

    with tab3:
        st.subheader("重置密码")
        reset_user = st.text_input("用户名", placeholder="请输入要找回的用户名", key="reset_user")
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

# -------------------------- 已登录主界面（仅优化角色保存逻辑，功能/界面不变） --------------------------
else:
    if "AI_name" not in st.session_state:
        st.session_state.AI_name = DEFAULT_AI_NAME
    if "AI_character" not in st.session_state:
        st.session_state.AI_character = DEFAULT_AI_CHARACTER

    # 核心修改：仅调整间距，不影响任何元素的背景样式
    st.markdown("""
    <style>
    /* 1. 压缩页面整体顶部空白（所有内容上移） */
    .block-container {
        padding-top: 2.5rem !important;  /* 大幅减少顶部空白，默认2rem */
        padding-bottom: 1rem !important;
    }
    /* 2. 压缩标题的上下间距 */
    h1 {
        margin-top: -10px !important;   /* 标题向上移 */
        margin-bottom: 5px !important;  /* 标题和下方文本间距缩小 */
    }
    /* 3. 压缩用户/会话信息文本的间距（仅调整位置，不改样式） */
    .user-session-text {
        margin-top: 0px !important;
        margin-bottom: 5px !important;
        font-size: 0.9rem;
    }
    /* 4. 优化聊天消息区域内边距，扩大显示空间 */
    .stChatMessage {
        padding: 0.5rem 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 标题（样式不变）
    st.title("AI智能伴侣")

    # Logo加载（完全不变）
    logo_file = "3.png"
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, logo_file)
    if os.path.exists(logo_path):
        st.logo(logo_path)

    now_time = datetime.now() + timedelta(hours=8)
    now_str = now_time.strftime("%Y年%m月%d日 %H:%M:%S")
    system_prompt_template = """
                            你是 %s。
                            角色设定：%s
                            当前真实时间：%s
                            请严格遵守以下回答规则：
                            1. 事实准确：不编造、不虚构、不猜测不确定信息，不确定时明确说明。
                            2. 时间正确：所有日期、时间、年龄、计时相关问题，必须使用上面提供的真实时间。
                            3. 内容完整：回答详细、充分、有逻辑，不简略、不敷衍、不使用短句糊弄。
                            4. 格式清晰：重点内容可以自然突出，步骤类问题分点说明，便于阅读。
                            5. 紧扣上下文：结合历史对话内容理解用户意图，不偏离当前对话场景。
                            6. 拒绝违规：不提供违法、危险、不道德、伤害性内容。
                            """

    # 修改：用户/会话信息 - 仅调整间距，保留原有样式
    st.markdown(f"""
    <div class="user-session-text">
    当前用户: {st.session_state.current_user} | 会话名称: {st.session_state.session_name}
    </div>
    """, unsafe_allow_html=True)

    # 显示聊天记录（关键：用st.info保留欢迎语原有背景样式，仅调整位置）
    if len(st.session_state.messages) == 0:
        # 无对话：显示欢迎语（保留原生st.info样式）
        st.info("👋 你好！我是你的AI智能伴侣，创建新对话时可在左侧修改我的设定，对话开始后无法更改，快来和我聊天吧～")
    else:
        # 有对话：只显示聊天记录，不显示欢迎语
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.chat_message("user").write(message["content"])
            else:
                st.chat_message("assistant").write(message["content"])

    with st.sidebar:
        st.subheader(f"当前用户：{st.session_state.current_user}")
        if st.button("退出登录", type="secondary", use_container_width=True, icon="🚪"):
            st.session_state.is_login = False
            st.session_state.current_user = ""
            st.session_state.messages = []
            st.session_state.session_name = generate_session_name()
            st.session_state.last_ai_name = DEFAULT_AI_NAME
            st.session_state.last_ai_char = DEFAULT_AI_CHARACTER
            if "AI_name" in st.session_state:
                del st.session_state.AI_name
            if "AI_character" in st.session_state:
                del st.session_state.AI_character
            st.rerun()

        st.divider()
        st.subheader("AI控制面板")

        if st.button("新建会话", width="stretch", icon="📝"):
            create_new_session(st.session_state.current_user)

        # 会话历史（优化按钮key，减少重复渲染）
        st.text("会话历史")
        session_list = load_sessions(st.session_state.current_user)
        for session in session_list:
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(session, width="stretch", icon="💬", 
                            key=f"load_{session}",  # 固定key，不随idx变
                            type="primary" if session == st.session_state.session_name else "secondary"):
                    load_session(st.session_state.current_user, session)
            with col2:  
                if st.button("", icon="❌", key=f"delete_{session}",
                        use_container_width=True):
                    delete_session(st.session_state.current_user, session)

        st.divider()
        # AI角色设置（优化：仅内容真正变化时才保存，打字不卡）
        st.subheader("伴侣信息")

        # 完全保留你的原始key逻辑，界面/交互不变
        ai_name_key = f"ai_name_{st.session_state.session_name}"
        ai_char_key = f"ai_char_{st.session_state.session_name}"

        AI_name = st.text_input(
            "名称",
            value=st.session_state.AI_name,
            placeholder="请输入伴侣的名称",
            key=ai_name_key
        )
        character = st.text_area(
            "角色设定",
            value=st.session_state.AI_character,
            placeholder="请输入伴侣的角色设定",
            key=ai_char_key
        )

        # 优化：仅当内容真正变化时才更新+保存，避免每打一个字都保存
        save_needed = False
        if AI_name != st.session_state.last_ai_name:
            st.session_state.AI_name = AI_name
            st.session_state.last_ai_name = AI_name
            save_needed = True
        if character != st.session_state.last_ai_char:
            st.session_state.AI_character = character
            st.session_state.last_ai_char = character
            save_needed = True
        
        # 批量保存，减少IO次数
        if save_needed:
            save_chat(st.session_state.current_user)

    # 消息输入框+AI交互（完全不变）
    prompt = st.chat_input("请输入您要问的问题：")
    if prompt:
        st.chat_message("user").write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        system_prompt = system_prompt_template % (st.session_state.AI_name, st.session_state.AI_character, now_str)
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": system_prompt}, *st.session_state.messages],
                stream=True,
                max_tokens=2000
            )

            def stream_generator():
                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_chat(st.session_state.current_user)

            st.chat_message("assistant").write_stream(stream_generator)
        except Exception as e:
            st.error(f"AI响应失败：{str(e)}")
