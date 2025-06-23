import json
import sys
import os

# 将项目根目录添加到sys.path，以确保可以无缝导入core等模块
# 这是一种常见的做法，使得脚本在不同位置执行时都能找到正确的模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import app_config
from core.knowledge_base import KnowledgeBase
from core.user_profile import UserProfile
from core.orchestrator import IntelligentTutorAgent
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.toolkits import FunctionTool
from camel.models import OpenAICompatibleModel
from core.tools_custom import save_knowledge_base

# 模块级的模型配置字典，用于在不同函数间共享状态
model_config = {
    "model_type": "Pro/deepseek-ai/DeepSeek-V3",
    "temperature": 0.5,
    "url": "https://api.siliconflow.cn/v1",
    "api_key": os.getenv("SILICONFLOW_API_KEY")
}

def _start_learning_session(user_profile: UserProfile):
    """处理学习会话的逻辑，现在是动态和交互式的。"""
    global model_config
    print("\n--- 开始新的学习会话 ---")
    print(f"--- 模型: {model_config['model_type']}, 温度: {model_config['temperature']} ---")
    
    user_profile.reset()
    tutor = IntelligentTutorAgent(user_profile, model_config=model_config)

    print("\n[导师]: 你好！你想学习什么？我们可以一起制定一个学习计划。")
    print("在对话中，你可以随时使用 'upload <文件路径>' 命令来上传参考材料。")
    print("输入 'quit' 或 'exit' 来结束当前学习会话。")

    while True:
        try:
            user_input = input("\n[你]: ").strip()
            if not user_input: continue
            
            if user_input.lower() in ['quit', 'exit']:
                print("\n[导师]: 好的，本次学习结束。")
                break
            
            # --- 新增：处理上传命令 ---
            if user_input.lower().startswith("upload "):
                file_path = user_input[7:].strip()
                if not os.path.exists(file_path):
                    print(f"[导师]: 错误：找不到文件 '{file_path}'。")
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    tutor.set_uploaded_material(file_content)
                    print("[导师]: 材料上传成功！它将在我们确定学习目标后，用于为您生成专属知识库。请继续对话。")
                    continue # 继续循环，等待下一个用户输入
                except Exception as e:
                    print(f"[导师]: 读取文件时出错: {e}")
                    continue
            
            assistant_response = tutor.step(user_input)
            print(f"\n[导师]: {assistant_response}")
        except (KeyboardInterrupt, EOFError):
            print("\n[导师]: 对话结束。")
            break

    print("\n" + "="*50 + "\n学习会话结束，正在生成您的学习报告...\n" + "="*50)
    if tutor.user_profile.knowledge_mastery:
        print(f"最终知识点掌握度: {json.dumps(tutor.user_profile.knowledge_mastery, indent=2, ensure_ascii=False)}")
        print(f"本次学习中识别出的误解: {json.dumps(tutor.user_profile.misconceptions_log, indent=2, ensure_ascii=False)}")
    else:
        print("本次会话没有产生学习记录。")
    print("\n" + "="*50)
    input("按任意键返回主菜单...")

def _set_model_config():
    """处理模型设置的逻辑"""
    global model_config
    print("\n--- 模型设置 ---")
    
    # 显示当前配置
    print(f"当前API平台URL: {model_config['url']}")
    print(f"当前模型名称: {model_config['model_type']}")
    print(f"当前温度: {model_config['temperature']}")
    # 为了安全，不直接显示API Key
    key_display = f"********{model_config['api_key'][-4:]}" if model_config.get('api_key') and len(model_config['api_key']) > 4 else "未设置"
    print(f"当前API Key: {key_display}")
    print("-" * 20)

    # 获取新配置
    new_url = input("请输入新的API平台URL (直接回车则不修改): ").strip()
    if new_url:
        model_config["url"] = new_url

    new_model = input("请输入新的模型名称 (直接回车则不修改): ").strip()
    if new_model:
        model_config["model_type"] = new_model
    
    new_api_key = input("请输入新的API Key (直接回车则不修改): ").strip()
    if new_api_key:
        model_config["api_key"] = new_api_key

    while True:
        new_temp_str = input(f"请输入新的温度 (0.0-2.0, 直接回车则不修改): ").strip()
        if not new_temp_str:
            break
        try:
            new_temp = float(new_temp_str)
            if 0.0 <= new_temp <= 2.0:
                model_config["temperature"] = new_temp
                break
            else:
                print("无效输入，温度必须在 0.0 和 2.0 之间。")
        except ValueError:
            print("无效输入，请输入一个数字。")

    print("\n设置已更新！")
    input("按任意键返回主菜单...")

def _review_session():
    """处理"复习"的逻辑 (占位符)"""
    print("\n--- 复习模式 ---")
    print("该功能正在全力开发中！")
    input("按任意键返回主菜单...")

def _import_materials(kb: KnowledgeBase):
    """处理"导入材料"的逻辑，支持创建和追加。"""
    global model_config
    print("\n--- 导入学习材料 ---")
    kb_names = kb.get_available_kb_names()
    print("当前可用的知识库:", ", ".join(kb_names) if kb_names else "无")
    topic_name = input("请输入知识库的主题名称 (如果名称已存在，则会追加内容): ").strip()
    if not topic_name:
        print("错误：主题名称不能为空。")
        input("按任意键返回主菜单..."); return

    file_path = input("请输入 .txt 或 .md 文件的完整路径: ").strip()
    if not os.path.exists(file_path):
        print(f"错误：找不到文件 '{file_path}'。")
        input("按任意键返回主菜单..."); return
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f: file_content = f.read()
    except Exception as e:
        print(f"读取文件时出错: {e}")
        input("按任意键返回主菜单..."); return
    
    print("文件读取成功。正在调用AI进行转换...")
    # ... (Agent调用逻辑与之前版本相同，省略) ...
    # ...
    
def _launch_webapp():
    """启动Streamlit Web应用"""
    print("\n--- 启动 Web 用户界面 ---")
    print("正在启动服务，请在您的浏览器中打开显示的URL。")
    print("在Web服务运行时，此命令行窗口将用于显示服务日志。")
    print("您可以随时在此窗口按 Ctrl+C 来停止Web服务。")
    os.system('streamlit run interfaces/app.py')
    print("\nWeb服务已停止。")
    input("按任意键返回主菜单...")

def run_cli():
    """
    运行基于数字菜单的命令行界面。
    """
    print("=== 通用学习导师 (命令行模式) ===")
    
    # 1. 检查配置
    if not app_config.siliconflow_api_key:
        print("\n错误: 未在.env文件中找到SILICONFLOW_API_KEY。")
        print("请确认项目根目录下存在.env文件，并且内容如下:")
        print('SILICONFLOW_API_KEY="sk-xxxxxxxx"')
        return
    
    # 2. 初始化一些不会变的组件
    # kb = KnowledgeBase() 
    user_profile = UserProfile("cli_user_01")

    # 3. 进入主菜单循环
    while True:
        print("\n" + "="*25 + " 主菜单 " + "="*25)
        print("  1. 开始新的学习主题\n  2. 复习已学知识\n  3. 导入学习材料\n  4. 模型设置\n  5. 启动 Web 用户界面\n  6. 退出")
        print("="*58)
        
        choice = input("请输入您的选项 (1-6): ").strip()

        if choice == '1':
            # 创建一个新的Agent实例开始会话
            # Agent会创建自己的知识库实例
            tutor = IntelligentTutorAgent(user_profile, model_config=model_config)
            _start_learning_session(user_profile)
        elif choice == '2':
            _review_session()
        elif choice == '3':
            # 导入材料也需要一个临时的Agent实例来访问其知识库
            temp_agent = IntelligentTutorAgent(user_profile, model_config=model_config)
            _import_materials(temp_agent.knowledge_base)
        elif choice == '4':
            _set_model_config()
        elif choice == '5':
            _launch_webapp()
        elif choice == '6':
            print("\n感谢使用，期待下次与您再会！")
            break
        else:
            print("\n无效选项，请重新输入。")
            input("按任意键继续...")

if __name__ == '__main__':
    run_cli() 