from typing import List, Dict, Any

# --- 模块2.2: 用户画像 ---
class UserProfile:
    """
    增强的用户画像模型。
    负责追踪学习者的所有状态，包括：
    - 定量掌握度 (knowledge_mastery)
    - 定性误解记录 (misconceptions_log)
    - 对话历史、学习风格等。
    这是 "核心B"、"核心C"、"核心D" 的关键输入。
    """
    def __init__(self, user_id: str):
        self.user_id = user_id
        # 定量追踪: 每个知识点的掌握度 (0.0 ~ 1.0)
        self.knowledge_mastery: Dict[str, float] = {}
        # 定量追踪: 每个知识点的最后复习时间 (Unix timestamp)
        self.last_review_time: Dict[str, float] = {}
        # 定性追踪: 每个知识点下出现的误解详情
        self.misconceptions_log: Dict[str, List[str]] = {}
        # 过程记录: 全部对话历史
        self.dialogue_history: List[Dict[str, str]] = []
        # 风格画像: 用户的学习风格标签 (预留)
        self.learning_style_tags: set = set()

    def reset(self):
        """
        重置用户的学习画像，以开始一个全新的学习会话。
        """
        print(f"[UserProfile] Resetting profile for user '{self.user_id}'...")
        self.knowledge_mastery.clear()
        self.last_review_time.clear()
        self.misconceptions_log.clear()
        self.dialogue_history.clear()
        # learning_style_tags is considered a long-term preference, so it's not reset. 