import json
from typing import Optional, Dict, Any

def parse_llm_json_output(content: str) -> Optional[Dict[str, Any]]:
    """
    安全地解析LLM输出的JSON字符串。
    能够处理包含在markdown代码块 (```json ... ```) 中的情况。

    Args:
        content: LLM返回的原始字符串。

    Returns:
        解析后的字典，如果解析失败则返回 None。
    """
    try:
        # 移除可能的markdown代码块标记
        if content.strip().startswith("```json"):
            content = content.strip()[7:-3].strip()
        return json.loads(content)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"[Parser] 错误: 解析LLM JSON输出失败。错误: {e}, 内容: {content}")
        return None 