import time
from typing import Dict, Any, Optional

# 确保在core包内导入时使用相对路径
from .user_profile import UserProfile
from .knowledge_base import KnowledgeBase

# --- 模块3: 分析与规划脑 ---
class AnalyticalPlanner:
    """
    分析脑（Planner）。
    负责宏观层面的学习路径规划。
    """
    def __init__(self, mastery_threshold=0.75):
        self.mastery_threshold = mastery_threshold

    def update_mastery(self, user_profile, concept_id, evaluation, force_mastery=False):
        """
        根据评估结果，定量更新用户对某个知识点的掌握度。
        这是一个简化的模型，实际应用中会更复杂。
        """
        if force_mastery:
            user_profile.knowledge_mastery[concept_id] = 1.0
            print(f"[Planner] Force-set mastery for '{concept_id}' to 1.0")
            return

        current_mastery = user_profile.knowledge_mastery.get(concept_id, 0.0)
        
        if evaluation == "correct":
            # 答对，掌握度大幅提升
            new_mastery = current_mastery + 0.4 * (1 - current_mastery)
        elif evaluation == "partially_correct":
            # 部分答对，掌握度少量提升
            new_mastery = current_mastery + 0.15 * (1 - current_mastery)
        elif evaluation in ["incorrect", "misconception"]:
            # 答错或有误解，掌握度少量下降
            new_mastery = current_mastery * 0.85
        else: # "not_applicable" 等
            new_mastery = current_mastery # 不变

        user_profile.knowledge_mastery[concept_id] = min(1.0, max(0.0, new_mastery))
        print(f"[Planner] Updated mastery for '{concept_id}': {current_mastery:.2f} -> {user_profile.knowledge_mastery[concept_id]:.2f}")

    def select_next_action(self, user_profile: UserProfile, knowledge_base: KnowledgeBase, current_concept_id: Optional[str]) -> Dict[str, Any]:
        """
        决策模块：根据用户当前状态，决定下一步行动。
        如果 current_concept_id 为 None，则从头开始寻找第一个未掌握的概念。
        """
        all_concepts = knowledge_base.get_concept_keys()
        if not all_concepts:
            return {"action": "finish", "concept_id": None}

        start_index = 0
        if current_concept_id:
            try:
                # If a concept is specified, start searching from the *next* one
                start_index = all_concepts.index(current_concept_id) + 1
            except ValueError:
                # If the current concept isn't in the list (edge case), start from the beginning
                start_index = 0
        
        # Find the next unmastered concept from the start_index
        for i in range(start_index, len(all_concepts)):
            next_concept_id = all_concepts[i]
            if user_profile.knowledge_mastery.get(next_concept_id, 0.0) < self.mastery_threshold:
                return {"action": "start_new", "concept_id": next_concept_id}

        # If we've checked all concepts from the start_index and all are mastered,
        # it means the session is complete.
        return {"action": "finish", "concept_id": None} 