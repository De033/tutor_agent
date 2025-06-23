import os
from dotenv import load_dotenv

# --- 模块1: 环境与配置 ---
load_dotenv()

class AppConfig:
    """
    应用配置类，负责加载和管理所有外部配置，如环境变量和API密钥。
    """
    def __init__(self):
        # camel-ai 库需要名为 SILICONFLOW_API_KEY 和 SILICONFLOW_BASE_URL 的环境变量
        self.siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY")
        self.siliconflow_base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.mineru_api_key = os.getenv("MINERU_API_KEY")
        
        # 设置环境变量供 CAMEL 库内部使用
        if self.siliconflow_api_key:
            os.environ["SILICONFLOW_API_KEY"] = self.siliconflow_api_key
        if self.siliconflow_base_url:
            os.environ["SILICONFLOW_BASE_URL"] = self.siliconflow_base_url
        if self.mineru_api_key:
            os.environ["MINERU_API_KEY"] = self.mineru_api_key

# 创建一个全局配置实例，方便其他模块直接导入使用
# from config.settings import app_config
app_config = AppConfig() 