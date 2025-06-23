import streamlit as st
import sys
import os
import re
import fitz  # PyMuPDF
import time

# 将项目根目录添加到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings_manager import load_config, save_config
from core.user_profile import UserProfile
from core.orchestrator import IntelligentTutorAgent

# --- 页面渲染函数 ---

def render_markdown_with_latex(content: str):
    """
    一个辅助函数，用于渲染包含LaTeX的Markdown内容。
    它会查找$$...$$或\\[...\\]块，并使用st.latex渲染它们，
    其余部分则使用st.markdown。它还会将 \\(...\\) 转换为 $...$ 以支持行内公式。
    """
    content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content)
    latex_pattern = re.compile(r"(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\])")
    parts = latex_pattern.split(content)
    
    for i, part in enumerate(parts):
        if not part:
            continue
        if i % 2 == 1:
            latex_content = part.strip('$[]\\')
            try:
                st.latex(latex_content)
            except st.errors.StreamlitAPIException as e:
                st.markdown(f"```latex\n{latex_content}\n```")
                st.error(f"无法渲染以下的LaTeX公式: {e}")
        else:
            st.markdown(part, unsafe_allow_html=True)

def render_learn_page():
    """渲染核心的学习对话页面，支持动态上传。"""
    st.header("与导师对话学习 💬")

    # 文件上传器
    uploaded_file = st.file_uploader(
        "可选：上传学习材料（.pdf, .txt, .md）来创建专属知识库", 
        type=['pdf', 'txt', 'md']
    )
    
    # 增加对last_processed_file_id的检查，防止因st.rerun导致的重复分析
    if uploaded_file is not None and uploaded_file.file_id != st.session_state.get('last_processed_file_id'):
        try:
            file_content = ""
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()

            if file_extension == ".pdf":
                with fitz.open(stream=uploaded_file.getvalue(), filetype="pdf") as doc:
                    file_content = "".join(page.get_text() for page in doc)
            else:  # .txt, .md
                file_content = uploaded_file.getvalue().decode("utf-8")

            if file_content.strip():
                with st.spinner(f"正在分析您上传的文件 '{uploaded_file.name}'... 这可能需要一些时间。"):
                    response = st.session_state.tutor.set_uploaded_material(file_content)
                
                # 分析成功后，记录下这个文件的ID
                st.session_state.last_processed_file_id = uploaded_file.file_id
                
                st.toast(f"✔️ 文件 '{uploaded_file.name}' 已成功上传并分析!", icon="👍")
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun() 
            else:
                st.warning(f"文件 '{uploaded_file.name}' 解析后内容为空。")
                # 即使文件为空，也记录ID，避免重复弹出警告
                st.session_state.last_processed_file_id = uploaded_file.file_id
                
        except Exception as e:
            st.error(f"处理文件 '{uploaded_file.name}' 时出错: {e}")
            # 如果处理失败，重置标志位，允许用户重新上传相同的文件
            st.session_state.last_processed_file_id = None

    # 显示已有的聊天记录
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            render_markdown_with_latex(message["content"])

    # 用户输入
    if prompt := st.chat_input("你好！想学点什么？或确认/修改以上学习计划。"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("导师正在思考..."):
                response = st.session_state.tutor.step(prompt)
            render_markdown_with_latex(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

def render_review_page():
    """渲染复习页面，实现Anki功能。"""
    st.header("间隔重复复习 🧠")
    
    tutor = st.session_state.tutor

    if not st.session_state.review_started:
        st.session_state.due_cards = tutor.review_manager.get_due_cards()
        st.session_state.current_card_index = 0
        st.session_state.show_answer = False
        if st.session_state.due_cards:
            st.session_state.review_started = True

    if not st.session_state.due_cards:
        st.success("🎉 恭喜！今天所有卡片都复习完啦！")
        st.balloons()
        return

    total_cards = len(st.session_state.due_cards)
    current_index = st.session_state.current_card_index
    
    st.progress((current_index) / total_cards, text=f"进度: {current_index}/{total_cards}")

    if current_index >= total_cards:
        st.success("🎉 太棒了！本轮复习已全部完成！")
        st.session_state.review_started = False
        if st.button("开始新一轮复习"):
            st.rerun()
        return

    card = st.session_state.due_cards[current_index]

    st.markdown("---")
    st.markdown(f"### 问题：\n> {card.question}")
    st.markdown("---")

    if st.session_state.show_answer:
        st.markdown(f"**答案：**\n\n{card.answer}")
        
        cols = st.columns(4)
        ratings = {"重来": "again", "困难": "hard", "良好": "good", "简单": "easy"}
        
        button_map = {
            "重来": ("again", cols[0]), "困难": ("hard", cols[1]),
            "良好": ("good", cols[2]), "简单": ("easy", cols[3])
        }
        for btn_text, (rating, col) in button_map.items():
            if col.button(btn_text, use_container_width=True):
                handle_review(rating, card.id)

        st.markdown("---")
        if st.button("🗑️ 删除这张卡片", use_container_width=True, key=f"delete_{card.id}"):
            handle_delete(card.id)
    else:
        if st.button("显示答案", use_container_width=True, type="primary"):
            st.session_state.show_answer = True
            st.rerun()

def handle_review(rating: str, card_id: str):
    """处理用户对卡片的评级。"""
    st.session_state.tutor.review_manager.update_card_review(card_id, rating)
    st.session_state.current_card_index += 1
    st.session_state.show_answer = False
    st.rerun()

def handle_delete(card_id: str):
    """处理删除卡片的逻辑。"""
    st.session_state.tutor.review_manager.delete_card(card_id)
    st.session_state.due_cards = [c for c in st.session_state.due_cards if c.id != card_id]
    st.session_state.show_answer = False
    st.rerun()

def init_session_state():
    """初始化Streamlit的session_state，现在由配置文件驱动。"""
    
    # 从配置文件加载配置，作为"唯一真实来源"
    if 'config' not in st.session_state:
        st.session_state.config = load_config()

    if 'tutor' not in st.session_state:
        model_config = st.session_state.config.get("model_config", {})
        if not model_config.get("api_key"):
            st.error("错误: 未找到API Key。请在 config/settings.json 或侧边栏高级设置中配置。")
            st.stop()
        
        user_id = st.session_state.config.get("app_settings", {}).get("default_user_id", "default_user")
        user_profile = UserProfile(user_id)
        
        st.session_state.tutor = IntelligentTutorAgent(
            user_profile,
            model_config=model_config
        )
        st.session_state.messages = []
    
    if 'page' not in st.session_state:
        st.session_state.page = '学习'
    
    if 'review_started' not in st.session_state:
        st.session_state.review_started = False
        st.session_state.due_cards = []
        st.session_state.current_card_index = 0
        st.session_state.show_answer = False
    
    if 'last_processed_file_id' not in st.session_state:
        st.session_state.last_processed_file_id = None

def main_webapp():
    """运行基于Streamlit的Web应用导师。"""
    st.set_page_config(page_title="智能导师 Agent", page_icon="🎓", layout="wide")
    
    init_session_state()

    with st.sidebar:
        st.title("🎓 智能导师")
        st.markdown("---")

        # --- 设置界面 ---
        with st.expander("⚙️ 高级设置", expanded=False):
            with st.form("settings_form"):
                st.write("模型配置")
                
                # 从会话状态中获取当前配置用于显示
                current_config = st.session_state.config.get("model_config", {})

                new_url = st.text_input(
                    "API 地址", 
                    value=current_config.get("url")
                )
                new_api_key = st.text_input(
                    "API 密钥", 
                    type="password",
                    value=current_config.get("api_key"),
                    placeholder="如果已设置环境变量则此处可留空"
                )
                new_model_type = st.text_input(
                    "模型名称",
                    value=current_config.get("model_type")
                )
                new_temperature = st.slider(
                    "模型温度 (Temperature)", 
                    min_value=0.0, max_value=2.0, step=0.1,
                    value=current_config.get("temperature", 0.5)
                )

                submitted = st.form_submit_button("✅ 应用并重启导师")
                if submitted:
                    # 更新配置字典
                    new_config_data = st.session_state.config.copy()
                    new_config_data["model_config"] = {
                        "url": new_url,
                        "api_key": new_api_key,
                        "model_type": new_model_type,
                        "temperature": new_temperature
                    }
                    
                    # 保存到 settings.json 文件
                    save_config(new_config_data)
                    
                    # 更新会话状态并强制重启
                    st.session_state.config = new_config_data
                    if 'tutor' in st.session_state:
                        del st.session_state.tutor
                    st.toast("设置已保存并应用！导师已重启。", icon="👍")
                    st.rerun()

        st.session_state.page = st.radio(
            "切换模式",
            ['学习', '复习'],
            index=0 if st.session_state.page == '学习' else 1,
            horizontal=True
        )
        st.markdown("---")
        
        # --- 学习者画像和复习统计 ---
        col1, col2 = st.columns(2)
        with col1:
            st.metric("待复习", f"{len(st.session_state.tutor.review_manager.get_due_cards())}")
        with col2:
            st.metric("总卡片", f"{len(st.session_state.tutor.review_manager.deck.cards)}")

    if st.session_state.page == '学习':
        render_learn_page()
    elif st.session_state.page == '复习':
        render_review_page()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main_webapp() 
