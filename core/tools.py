from core.knowledge_base import KnowledgeBase

class KnowledgeTools:
    """
    一个封装了与知识库操作相关工具的类。
    这个类的实例需要与一个KnowledgeBase实例绑定。
    """
    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base

    def load_knowledge_base_from_file(self, path: str) -> str:
        """
        这个工具可以从指定的JSON文件路径加载一个新的知识库。
        当用户表达出想要加载或切换知识库的意图时，你应该使用此工具。
        例如，如果用户说 "加载 history.json"，你应该调用此工具并设置 path="history.json"。

        Args:
            path: 要加载的知识库JSON文件的路径。

        Returns:
            一个描述操作结果的字符串，会直接展示给用户。
        """
        print(f"[Tool] 正在尝试从 '{path}' 加载知识库...")
        
        # 调用KnowledgeBase的加载方法
        success = self.knowledge_base.load_from_file(path)
        
        if success:
            response = f"已成功加载知识库 '{path}'。新的学习主题现在可用了。"
            # 获取新知识库中的概念列表
            new_concepts = list(self.knowledge_base.concepts.keys())
            if new_concepts:
                response += f" 可用主题: {', '.join(new_concepts)}"
            return response
        else:
            return f"加载知识库 '{path}' 失败。请检查文件路径或文件格式是否正确。" 