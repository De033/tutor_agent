import json
import os
from typing import Dict, Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

_config: Dict[str, Any] = {}

def load_config() -> Dict[str, Any]:
    """
    Loads the configuration from settings.json.
    If the file doesn't exist, it creates a template file.
    It also allows overriding the API key with an environment variable.
    """
    global _config
    if _config:
        return _config

    if not os.path.exists(CONFIG_PATH):
        print(f"Configuration file {CONFIG_PATH} not found, creating a template.")
        default_config = {
            "model_config": {
                "url": "https://api.siliconflow.cn/v1",
                "api_key": "",  # To be filled by the user or environment variable
                "model_type": "deepseek-ai/deepseek-coder-v2-instruct",
                "temperature": 0.5
            },
            "app_settings": {
                "default_user_id": "webapp_user_01"
            }
        }
        save_config(default_config)
        _config = default_config
    else:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _config = json.load(f)
    
    # Allow environment variables to override config for security and flexibility
    api_key_from_env = os.getenv("OPENAI_COMPATIBLE_API_KEY")
    if api_key_from_env:
        _config["model_config"]["api_key"] = api_key_from_env
        
    api_base_from_env = os.getenv("OPENAI_COMPATIBLE_API_BASE")
    if api_base_from_env:
        _config["model_config"]["url"] = api_base_from_env

    return _config

def save_config(config_data: Dict[str, Any]):
    """Saves the configuration data back to the settings.json file."""
    global _config
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4)
    _config = config_data  # Update the in-memory cache 