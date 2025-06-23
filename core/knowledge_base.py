import os
import json
import difflib
from typing import Dict, Any, Optional, List, Tuple

KB_DIRECTORY = "knowledge_bases"

class KnowledgeBase:
    """
    知识库管理器。
    负责扫描、加载和管理多个知识库文件。
    """
    def __init__(self):
        self.available_kbs: Dict[str, str] = {}  # {topic_name: file_path}
        self.concepts: Dict[str, Any] = {}
        self.current_kb_name: Optional[str] = None
        self.current_kb_path: Optional[str] = None
        
        if not os.path.exists(KB_DIRECTORY):
            os.makedirs(KB_DIRECTORY)
            
        self.scan_for_kbs()

    def scan_for_kbs(self):
        """扫描知识库目录，更新可用的知识库列表。"""
        self.available_kbs.clear()
        try:
            for filename in os.listdir(KB_DIRECTORY):
                if filename.endswith(".json"):
                    topic_name = filename[:-5].replace('_', ' ').title()
                    self.available_kbs[topic_name] = os.path.join(KB_DIRECTORY, filename)
        except FileNotFoundError:
            print(f"Warning: Knowledge base directory '{KB_DIRECTORY}' not found.")
        print(f"[KnowledgeBase] Found available KBs: {list(self.available_kbs.keys())}")

    def get_available_kb_names(self) -> List[str]:
        """返回所有可用知识库的规范名称列表。"""
        return list(self.available_kbs.keys())

    def load_kb_by_topic(self, topic_name: str) -> Tuple[bool, str]:
        """根据主题名称模糊匹配并加载知识库。"""
        matches = difflib.get_close_matches(topic_name, list(self.available_kbs.keys()), n=1, cutoff=0.6)
        
        if not matches:
            return False, f"No similar KB found for topic '{topic_name}'."
        
        matched_topic = matches[0]
        file_path = self.available_kbs[matched_topic]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
            
            if not isinstance(kb_data, dict):
                raise json.JSONDecodeError("KB file root is not a JSON object.", "", 0)

            # Handle new standard format: {"concepts": {...}}
            if "concepts" in kb_data:
                self.concepts = kb_data.get("concepts", {})
            # Handle old legacy format: {"concepts_list": [...]}
            elif "concepts_list" in kb_data:
                self.concepts = {item['name']: item for item in kb_data.get('concepts_list', [])}
            # Handle legacy flat format, where the root is the concepts dict
            else:
                self.concepts = kb_data
            
            self.current_kb_name = matched_topic
            self.current_kb_path = file_path
            print(f"[KnowledgeBase] Successfully loaded KB '{matched_topic}' from '{file_path}'.")
            return True, f"Successfully loaded '{matched_topic}'."
        except (IOError, json.JSONDecodeError) as e:
            self.concepts = {}
            self.current_kb_name = None
            self.current_kb_path = None
            return False, f"Error loading or parsing KB file: {e}"

    def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """
        Gets the details for a specific concept ID.
        This is hardened to handle inconsistent KB formats where concept
        details might be wrapped in a list.
        """
        if not isinstance(self.concepts, dict):
            return None

        concept_data = self.concepts.get(concept_id)
        
        # Handle cases where the value for a concept key is a list containing the dict
        if isinstance(concept_data, list):
            if len(concept_data) > 0 and isinstance(concept_data[0], dict):
                return concept_data[0]
            else:
                return None

        if isinstance(concept_data, dict):
            return concept_data

        return None

    def get_concept_keys(self) -> List[str]:
        """获取所有概念的ID列表。"""
        if isinstance(self.concepts, dict):
            return list(self.concepts.keys())
        return []

    def check_kb_validity(self, topic_name: str) -> Tuple[bool, str]:
        """
        检查指定主题的知识库文件是否存在、可解析且包含有效内容。

        Returns:
            Tuple[bool, str]: (是否有效, 原因)
        """
        # 1. 扫描最新的文件列表
        self.scan_for_kbs()
        
        # 2. 查找匹配的文件
        matches = difflib.get_close_matches(topic_name, list(self.available_kbs.keys()), n=1, cutoff=0.8) # Stricter cutoff
        if not matches:
            return False, f"知识库 '{topic_name}' 不存在或名称不匹配。"

        file_path = self.available_kbs[matches[0]]

        # 3. 检查文件是否可读和可解析
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 检查文件是否为空
                if os.fstat(f.fileno()).st_size == 0:
                    return False, "知识库文件为空。"
                data = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            return False, f"无法读取或解析JSON文件: {e}"

        # 4. 检查内容结构和非空
        if not isinstance(data, dict):
            return False, "知识库顶层结构必须是一个JSON对象。"
        
        concepts = data.get("concepts")
        if not concepts:
            return False, "知识库JSON中缺少 'concepts' 键。"
        
        if not isinstance(concepts, dict):
            return False, "'concepts' 的值必须是一个JSON对象。"
            
        if not concepts: # Check if the concepts dictionary is empty
            return False, "'concepts' 对象为空，没有学习概念。"
            
        return True, "知识库有效。"

    def reload(self):
        """重新扫描并加载所有知识库。"""
        print("[KnowledgeBase] Reloading all knowledge bases...")
        self.scan_for_kbs()

    def reload_current_kb(self):
        """仅重新加载当前活动的知识库文件。"""
        if self.current_kb_name:
            print(f"[KnowledgeBase] Reloading current KB: {self.current_kb_name}")
            try:
                # We use load_kb_by_topic to ensure consistent loading logic
                loaded, reason = self.load_kb_by_topic(self.current_kb_name)
                if not loaded:
                    print(f"Failed to reload {self.current_kb_name}: {reason}")
            except Exception as e:
                print(f"Error reloading KB file {self.current_kb_path}: {e}")
                self.concepts = {}
        else:
            print("[KnowledgeBase] No current KB path set, cannot reload.")

    @property
    def is_loaded(self) -> bool:
        """检查当前是否有加载的知识库。"""
        return bool(self.concepts) 