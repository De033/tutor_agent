import json
import os
from typing import Optional, Dict, Any, List
from enum import Enum
import re
import difflib
from pydantic import BaseModel, Field

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import OpenAICompatibleModel
from camel.toolkits import FunctionTool

from core.user_profile import UserProfile
from core.knowledge_base import KnowledgeBase
from core.planner import AnalyticalPlanner
from utils.parsers import parse_llm_json_output
from core.tools_custom import save_knowledge_base, add_concept_to_kb
from core.review_manager import ReviewManager, Flashcard

# --- 结构化输出 ---
class Concept(BaseModel):
    definition: str = Field(..., description="The clear and concise definition of the concept.")
    example: str = Field(..., description="A simple and illustrative example of the concept.")
    socratic_prompts: List[str] = Field(..., min_length=2, description="A list of at least two Socratic questions to guide the user's thinking.")
    difficulty: int = Field(..., ge=1, le=5, description="The difficulty of the concept, rated from 1 (easiest) to 5 (hardest).")

class KnowledgeBaseModel(BaseModel):
    concepts: Dict[str, Concept] = Field(..., description="A dictionary where keys are the names of the sub-topics and values are their detailed concept structures.")

class ResponseStrategy(str, Enum):
    """Enumeration of possible high-level teaching strategies."""
    ANSWER_QUESTION = "answer_question"
    PROGRESS_TO_NEXT_CONCEPT = "progress_to_next_concept"
    REVIEW_AND_CLARIFY = "review_and_clarify"
    SOCRATIC_GUIDANCE = "socratic_guidance"
    CONSOLIDATE_AND_VERIFY = "consolidate_and_verify"
    HANDLE_IRRELEVANCE = "handle_irrelevance"
    FOLLOW_USER_LEAD = "follow_user_lead"
    ACKNOWLEDGE_AND_WAIT = "acknowledge_and_wait"

class Action(BaseModel):
    """A specific action to be executed by the Guidance Agent."""
    action_type: str = Field(..., description="The type of action, e.g., 'ask_question', 'explain'.")
    content: str = Field(..., description="The content for the action, e.g., the question text or explanation.")

class FullPedagogicalDecisionModel(BaseModel):
    """A comprehensive model for the pedagogical agent's decision."""
    analysis: str = Field(..., description="A brief, internal analysis of the user's input and current state. This is your scratchpad for thinking.")
    response_strategy: ResponseStrategy = Field(..., description="The chosen high-level strategy for this turn.")
    action: Action = Field(..., description="The specific action to be taken to implement the strategy.")

class FlashcardContent(BaseModel):
    """A Pydantic model to structure the output of the FlashcardGeneratorAgent."""
    question: str = Field(..., description="The 'front' of the flashcard, posing a single, clear question.")
    answer: str = Field(..., description="The 'back' of the flashcard, providing a concise and accurate answer.")

class FlashcardBatch(BaseModel):
    """A Pydantic model for receiving a batch of flashcards from the generator agent."""
    cards: List[FlashcardContent] = Field(..., description="A list of generated flashcard question-answer pairs.")

class CardableDetails(BaseModel):
    """A model to determine if there are card-worthy details in a conversation."""
    has_cardable_details: bool = Field(..., description="True if specific, atomic facts were mentioned that are suitable for a new flashcard.")



# --- 模块4: 智能导师Agent (编排器) ---
class TutorState(Enum):
    IDLE = 0
    ANALYZING_GOAL = 1
    GENERATING_KB = 2
    TUTORING = 3
    AWAITING_PLAN_CONFIRMATION = 4
 # 状态机 
class IntelligentTutorAgent:
    """
    一个动态的、围绕对话生成教学内容的智能导师。
    实现了从定义学习目标、动态生成知识库到个性化教学的完整流程。
    """
    def __init__(self, user_profile: UserProfile,
                 model_config: Dict[str, Any]):
        self.user_profile = user_profile
        self.knowledge_base = KnowledgeBase()
        self.current_concept_id: Optional[str] = None
        self.analytical_planner = AnalyticalPlanner()
        self.review_manager = ReviewManager(user_profile)
        self.state = TutorState.IDLE
        self.learning_blueprint: Dict[str, Any] = {
            "status": "incomplete", "topic": None, "sub_topics": [], 
            "current_level": "unknown", "learning_style": "unknown"
        }
        self.uploaded_material: Optional[str] = None
        self.history: List[Dict[str, Any]] = []
        
        self.model_instance = OpenAICompatibleModel(
            model_type=model_config.get("model_type"),
            url=model_config.get("url"),
            model_config_dict={"temperature": model_config.get("temperature")},
            api_key=model_config.get("api_key"),
        )

        self.goal_analyzer_agent = self._create_goal_analyzer_agent()
        self.kb_creator_agent = self._create_kb_creator_agent()
        self.guidance_agent = self._create_guidance_agent()
        self.content_analyzer_agent = self._create_content_analyzer_agent()
        self.intent_classifier_agent = self._create_intent_classifier_agent()
        self.strategy_agent = self._create_pedagogical_strategy_agent()
        self.flashcard_decision_agent = self._create_flashcard_decision_agent()
        self.single_flashcard_agent = self._create_single_flashcard_agent()

    def _create_goal_analyzer_agent(self) -> ChatAgent:
        system_prompt = """你是一位顶级的学习顾问。你的目标是通过对话，引导用户明确他们的学习需求，并生成一个结构化的JSON"学习需求清单"。
严格遵循以下对话流程和JSON格式：
1.  **问候与启动**: 当用户表达学习意愿时，热情问候并开始提问。
2.  **探寻主题 (topic)**: 首先询问用户想学习的大主题是什么。
3.  **探寻子主题 (sub_topics)**: 引导用户列出希望覆盖的具体知识点。
4.  **评估水平 (current_level)**: 询问用户的现有水平（初学者、有一定基础、专家）。
5.  **确认风格 (learning_style)**: 询问用户偏好的学习风格（例如：苏格拉底式、多一些实例、快速直接）。
6.  **检查确认**: 在收集完所有信息后，向用户汇总并请求确认。
7.  **最终输出**: 一旦用户确认，严格按照以下JSON格式输出，不要有任何额外文字。

{
  "status": "complete" | "incomplete",
  "topic": "string | null",
  "sub_topics": ["string 1", "string 2", ...] | [],
  "current_level": "beginner" | "intermediate" | "advanced" | "unknown",
  "learning_style": "socratic" | "example_driven" | "direct" | "unknown",
  "next_question": "string_next_question_to_ask_user"
}
"""
        return ChatAgent(
            BaseMessage.make_assistant_message("Learning Goal Analyzer", system_prompt),
            model=self.model_instance
        )

    def _create_intent_classifier_agent(self) -> ChatAgent:
        system_prompt = """You are a highly-focused intent classifier. Your task is to analyze a user's response to a proposed learning plan and classify their intent.

You have just presented the user with a learning plan and asked for their confirmation (e.g., "I've created this plan for you, what do you think?"). Now you need to understand their reply.

Strictly output a JSON object with a single key "intent" and one of the following three values:
- "confirm": The user agrees with the plan and wants to proceed. Examples: "yes", "ok", "good", "let's start", "开始学习", "好的", "可以", "没问题", "就这么办".
- "reject": The user wants to change the plan or has expressed dissatisfaction. Examples: "no", "not good", "change", "不对", "调整一下", "我想改一下".
- "unclear": The user's response is ambiguous, off-topic, or a question. Examples: "How long will this take?", "为什么是这些主题？".

Example 1:
User says: "Looks great, let's do it!"
Your output: {"intent": "confirm"}

Example 2:
User says: "Hmm, can we add a section on recursion?"
Your output: {"intent": "reject"}

Example 3:
User says: "开始学习吧"
Your output: {"intent": "confirm"}
"""
        return ChatAgent(
            BaseMessage.make_assistant_message("Intent Classifier", system_prompt),
            model=self.model_instance
        )

    def _create_content_analyzer_agent(self) -> ChatAgent:
        system_prompt = """你是一位顶级的课程规划师和内容分析专家。你的任务是分析用户提供的文本材料，并从中提炼出一个结构化的"学习蓝图"。

核心任务：
1.  **通读全文**：仔细阅读用户上传的全部材料，理解其核心主题和内容结构。
2.  **提炼主题**：确定这份材料最核心的主题 (topic)。
3.  **划分章节**：将材料内容逻辑地划分为多个子主题 (sub_topics)，这应该类似于一本书的目录。
4.  **评估难度和风格**：根据内容的深度和表达方式，评估整体内容的学习难度 (current_level: 'beginner', 'intermediate', 'advanced') 和最适合的教学风格 (learning_style: 'socratic', 'example_driven', 'direct')。
5.  **生成总结和确认请求**：创建一段面向用户的文本 (user_facing_summary)，用友好的语气总结你规划的学习蓝图，并请求用户确认。例如："我分析了您上传的文件，它似乎是关于'线性代数'的。我为您规划了以下学习路径：[子主题1, 子主题2, ...]。您觉得这个计划如何？如果没问题，我们就可以基于这个计划为您创建详细的知识库了。"
6.  **严格的JSON输出**：将你的所有分析结果严格封装在一个JSON对象中，格式如下，不要有任何额外文字。

{
  "learning_blueprint": {
    "status": "pending_confirmation",
    "topic": "string",
    "sub_topics": ["string 1", "string 2", ...],
    "current_level": "beginner" | "intermediate" | "advanced",
    "learning_style": "socratic" | "example_driven" | "direct"
  },
  "user_facing_summary": "string"
}
"""
        return ChatAgent(
            BaseMessage.make_assistant_message("Content Analyzer", system_prompt),
            model=self.model_instance
        )

    def _create_pedagogical_strategy_agent(self) -> ChatAgent:
        system_prompt = """You are an expert pedagogical strategist for a one-on-one AI tutor. Your role is to be the 'brain' of the tutor, deciding the best next step based on a comprehensive analysis of the learning context.

You will receive a JSON object containing the full context: the user's latest message, the current learning concept, the user's mastery level of that concept, and the conversation history.

Your task is to THINK step-by-step and then produce a SINGLE, VALID JSON object conforming to the `FullPedagogicalDecisionModel`.

**Your Thought Process (for the 'analysis' field):**
1.  **Analyze User's Intent:** What is the user trying to do? Are they asking a question? Answering my last question? Giving a command? Making a generic comment? Confused?
2.  **Evaluate User's Knowledge:** If they answered a question, how correct is it? Does it reveal misconceptions?
3.  **Consider Learning State:** What is their mastery level? Is it time to move on? Do we need to review?
4.  **Select a Strategy:** Based on the above, choose the most appropriate `ResponseStrategy` value (e.g., "answer_question", "progress_to_next_concept").
5.  **Formulate an Action:** Define the concrete `Action` that the tutor should say to the user.

**Strategy Guide & Output Format:**

*   **`answer_question`**: Used for direct questions.
*   **`progress_to_next_concept`**: Used when mastery is high.
*   **`review_and_clarify`**: Used for incorrect answers.
*   **`socratic_guidance`**: Used for partially correct answers.
*   **`consolidate_and_verify`**: Used for correct answers.
*   **`follow_user_lead`**: Used for user commands.
*   **`handle_irrelevance`**: Used for off-topic chat.
*   **`acknowledge_and_wait`**: Used for simple acknowledgements.

**IMPORTANT: Your final output must be ONLY the JSON object. The structure must be PERFECT.**
- The `response_strategy` field must contain one of the exact lowercase string values from the strategy guide (e.g., `"consolidate_and_verify"`).
- The `action` field MUST be a dictionary with two keys: `action_type` (a string) and `content` (a string).

**EXAMPLE of a PERFECT output:**
```json
{
  "analysis": "The user correctly answered the question, showing good understanding. I should consolidate this knowledge with a follow-up question.",
  "response_strategy": "consolidate_and_verify",
  "action": {
    "action_type": "ask_question",
    "content": "That's exactly right! Can you explain why that is the case?"
  }
}
```
"""
        return ChatAgent(
            BaseMessage.make_assistant_message("PedagogicalStrategist", system_prompt),
            model=self.model_instance
        )

    def _create_kb_creator_agent(self) -> ChatAgent:
        system_prompt = """你是一位顶级的教学设计师。你的任务是根据给定的"学习需求清单"和可选的用户上传材料，创建一个结构化的JSON知识库。
核心任务:
1.  **分析需求**: 理解需求清单中的每一个字段，尤其是 `sub_topics`。
2.  **融合材料**: 如果用户提供了补充材料，优先基于这些材料来构建知识点。
3.  **主动扩展**: 如果没有材料或材料不充分，你需要利用你自己的知识来创建内容。
4.  **结构化输出**: 为`sub_topics`列表中的每一个子主题，生成一个详细的条目，包含 "definition", "example", "socratic_prompts" (一个至少包含两个问题的字符串列表), 和 "difficulty" (难度系数, 1-5的整数)。
5.  **最终输出**: 你的最终输出必须是一个严格遵循指定格式的JSON对象，不要添加任何额外的文字、叙述或解释。
**至关重要**: 整个输出必须是一个JSON对象，且只包含一个顶级键 "concepts"，其值为所有子主题组成的字典。
"""
        # 注意：该代理的唯一任务是生成有效的 Pydantic 对象。
        return ChatAgent(
            BaseMessage.make_assistant_message("Instructional Designer", system_prompt),
            model=self.model_instance
        )
    
    def _create_guidance_agent(self) -> ChatAgent:
        system_prompt = """你是一位专业的、富有同理心的通用学习助手。
你的核心任务是**严格执行**来自你的"教学策略师"提供的教学计划。你收到的指令会非常明确，包含了回应的语气、要执行的动作以及具体内容。

**你的工作流程:**
1.  **接收指令**: 你会得到一个包含 `strategy_name`, `spoken_response_style`, `next_action_type`, `action_details` 的JSON对象，以及用户的原始回复。
2.  **理解并执行**:
    -   **首要原则**: 如果收到的策略是 `FollowStudentLead`，请忽略`action_details`中的通用指令，优先分析用户的原始回复，并尽力满足他们的要求。
    -   **工具使用**: 如果用户的意图是学习一个当前知识库中不存在的新概念 (例如 "我想学习一下Python的列表推导式"), 你 **必须** 使用 `add_concept_to_kb` 工具。为了调用此工具，你首先需要自行生成该概念的 `definition`, `example`, `socratic_prompts` 和 `difficulty`。然后，你必须从对话历史中推断出当前的 `topic` (例如 "Python基础")，并将所有这些参数一并传入工具。
    -   **常规执行**: 对于其他策略，采用 `spoken_response_style` 指定的语气，并执行 `action_details` 中描述的具体行动。
3.  **自然回应**: 你的所有回复都应自然、流畅，像一个真正的导师。
"""
        # 创建工具实例
        add_concept_tool = FunctionTool(add_concept_to_kb)

        return ChatAgent(
            BaseMessage.make_assistant_message("Guidance Agent", system_prompt),
            model=self.model_instance,
            tools=[add_concept_tool] 
        )

    def _create_flashcard_decision_agent(self) -> ChatAgent:
        system_prompt = """You are an assistant that checks if a conversation snippet is complete enough to be a flashcard.
The user and AI have just had an exchange. Your task is to determine if this exchange represents a clear, self-contained piece of information suitable for a Question-Answer flashcard.

- If the AI has just clearly answered a user's question or explained a concept, and the user's response is a simple acknowledgment, respond with 'YES'.
- If the discussion is ongoing, incomplete, a command, or trivial social chat, respond with 'NO'.

Only respond with the word 'YES' or 'NO'.

Example 1:
User: "What is a python dictionary?"
AI: "A dictionary in Python is a collection of key-value pairs. Each key is connected to a value, and you can use a key to look up its corresponding value."
Your output: YES

Example 2:
User: "Ok got it, so what about lists?"
AI: "Great question! A list is an ordered collection of items."
Your output: NO (The user has immediately changed topic, the previous exchange was just an ack)

Example 3:
User: "That's cool."
AI: "I'm glad you think so! Do you have any other questions?"
Your output: NO (Trivial social chat)
"""
        return ChatAgent(
            BaseMessage.make_assistant_message("FlashcardDecisionAgent", system_prompt),
            model=self.model_instance,
        )

    def _create_single_flashcard_agent(self) -> ChatAgent:
        system_prompt = """你是一位精通"概念/描述框架 (CDF)"的学习专家。你的任务是将提供的对话解构成一组结构化、高质量的闪卡。

**你的思维流程：**
1.  **识别核心`概念`**：精确定位正在讨论的主要名词或思想。
2.  **提取`描述符`**：找到与"概念"相关的所有属性、定义、功能或问题。
3.  **构建自然语言问题**：为每一个`描述符`，构建一个**自然的、口语化的问题**。这个问题必须清晰地包含`概念`和`描述符`的关键词。
4.  **提供详尽答案**：`answer` 必须是清晰、具有描述性且内容完整的解释。

**关键规则：**
*   **问题必须是自然的问句**，而不是生硬的 `::` 拼接格式。
*   答案必须具有描述性和解释性。
*   你的最终输出必须是一个只包含 "cards" 列表的JSON对象，不含任何其他文字。

---
**示例：**

**对话内容：**
AI: "Python中的字典是一种无序的、可变的键值对集合。所谓'可变'，就是指你可以在创建之后修改它。"

**你的分析 (内部模拟):**
*   核心概念: `Python 字典`
*   描述符 1: `定义`
*   描述符 2: `可变性 (Mutability)`

**你的JSON输出:**
```json
{
  "cards": [
    {
      "question": "Python 字典的`定义`是什么？",
      "answer": "它是一种内置的Python数据结构，用于将条目存储为键值对的集合，并且是无序和可变的。"
    },
    {
      "question": "我们应该如何理解 Python 字典的`可变性(Mutability)`？",
      "answer": "所谓'可变'，是指字典的内容可以在创建后被修改，例如通过添加、更新或删除键值对。"
    }
  ]
}
```
---
"""
        return ChatAgent(
            BaseMessage.make_assistant_message("SingleFlashcardAgent", system_prompt),
            model=self.model_instance,
        )

    def set_uploaded_material(self, content: str) -> str:
        """
        Stores the content of an uploaded file and triggers the analysis process.
        This is the primary entry point when a user uploads a document.
        """
        self.uploaded_material = content
        # 立即分析内容并返回摘要以供确认
        # 用户的下一个消息将是确认/拒绝计划
        return self._handle_goal_analysis(user_response="")

    def step(self, user_response: str) -> str:
        """
        The main entry point for the user's conversational turn.
        Orchestrates the agent's response based on its current state.
        """

        response = ""
        if self.state == TutorState.IDLE:
            # 学习过程的开始，用户上传文件或直接告诉我他想要学习什么
            response = self._handle_goal_analysis(user_response)
        elif self.state == TutorState.ANALYZING_GOAL:
            # 在对话中定义学习目标
            response = self._handle_goal_analysis(user_response)
        elif self.state == TutorState.AWAITING_PLAN_CONFIRMATION:
            # 用户正在响应提出的学习计划
            response = self._handle_plan_confirmation(user_response)
        elif self.state == TutorState.TUTORING:
            # 正在进行一个活跃的辅导会话
            response = self._handle_tutoring(user_response)
        
        return response

    def _handle_goal_analysis(self, user_response: str) -> str:
        # 意图检测，处理直接请求知识库列表
        list_kb_triggers = ["知识库", "你能教什么", "有哪些主题", "你会什么", "你能做什么"]
        if any(trigger in user_response for trigger in list_kb_triggers):
            available_kbs = self.knowledge_base.get_available_kb_names()
            if available_kbs:
                response = f"我目前可以教授以下主题：\n- **{', '.join(available_kbs)}**\n\n您想学习哪一个？或者，您也可以通过上传文件或告诉我一个新主题来创建全新的课程。"
            else:
                response = "我的知识库目前是空的。您可以通过上传文件或直接告诉我您想学习的主题来创建一个新的知识库。"
            self._add_to_history("assistant", response)
            return response

        # 如果上传了材料，首先使用内容分析器提出学习计划
        if self.uploaded_material:
            print("[Orchestrator] Found uploaded material, analyzing content...")
            analyzer_response = self.content_analyzer_agent.step(self.uploaded_material)
            
            # 处理后清除材料以避免重新分析
            self.uploaded_material = None 

            parsed_result = parse_llm_json_output(analyzer_response.msg.content)
            if not parsed_result or "learning_blueprint" not in parsed_result:
                return "抱歉，分析您提供的材料时遇到了问题。您能重新上传或直接告诉我您想学什么吗？"

            self.learning_blueprint = parsed_result["learning_blueprint"]
            user_summary = parsed_result.get("user_facing_summary", "我分析了您的文档，我们可以开始学习吗？")
            
            self.state = TutorState.AWAITING_PLAN_CONFIRMATION
            return user_summary

        # 没有上传材料，使用目标分析器
        print("[Orchestrator] No uploaded material, using Goal Analyzer.")
        # 更新学习需求清单
        self.learning_blueprint["last_user_response"] = user_response
        
        # 将学习需求清单和用户回复传递给目标分析器
        prompt = f"""
        这是我们当前的学习需求清单，其中有些信息可能缺失了:
        ```json
        {json.dumps(self.learning_blueprint, ensure_ascii=False, indent=2)}
        ```
        这是用户刚刚的回复: "{user_response}"
        请根据用户的回复更新清单，然后决定下一步是继续提问还是确认完成。
        如果所有字段都已填充，请将status设为'complete'并最终确认一次。否则，请提出下一个问题。
        """
        analyzer_response = self.goal_analyzer_agent.step(BaseMessage.make_user_message("User", prompt))

        if not analyzer_response or not analyzer_response.msgs:
            response = "抱歉，我在分析您的学习目标时遇到了问题，请再说一遍好吗？"
            self._add_to_history("assistant", response)
            return response

        response_text = analyzer_response.msgs[0].content
        analysis_json = parse_llm_json_output(response_text)

        if not analysis_json:
            self._add_to_history("assistant", response_text)
            return response_text

        self.learning_blueprint.update(analysis_json)
        print(f"[Orchestrator] Learning blueprint updated: {self.learning_blueprint}")

        if self.learning_blueprint.get("status") == "complete":
            self.state = TutorState.GENERATING_KB
            return self._generate_kb_and_start()
        else:
            next_question = self.learning_blueprint.get("next_question", "我应该问什么呢？")
            self._add_to_history("assistant", next_question)
            return next_question

    def _handle_plan_confirmation(self, user_response: str) -> str:
        """Handles user confirmation for the auto-generated learning plan using an LLM for intent classification."""
        prompt = f"""The user was just shown a learning plan I generated. Now they have replied with: "{user_response}". Please classify their intent based on your instructions."""
        
        classifier_response = self.intent_classifier_agent.step(BaseMessage.make_user_message("User", prompt))

        # 如果LLM失败，回退到关键词，错误处理方式
        if not classifier_response or not classifier_response.msgs:
            if any(keyword in user_response.lower() for keyword in ["no", "不了", "改", "调整"]):
                intent = "reject"
            elif any(keyword in user_response.lower() for keyword in ["yes", "ok", "好", "可以", "没问题", "确认", "great", "looks good", "开始", "学习"]):
                intent = "confirm"
            else:
                intent = "unclear"
        else:
            intent_json = parse_llm_json_output(classifier_response.msgs[0].content)
            intent = intent_json.get("intent") if intent_json else "unclear"

        if intent == "confirm":
            print("[Orchestrator] User confirmed the learning plan.")
            self.learning_blueprint["status"] = "complete"
            self.state = TutorState.GENERATING_KB
            self._add_to_history("assistant", "太好了！我将根据这个计划为您创建详细的知识库，请稍候...")
            return self._generate_kb_and_start()

        elif intent == "reject":
            print("[Orchestrator] User rejected the learning plan.")
            self.state = TutorState.ANALYZING_GOAL
            self.learning_blueprint = { "status": "incomplete", "topic": None, "sub_topics": [], "current_level": "unknown", "learning_style": "unknown" }
            response = "好的，我们来调整一下计划。请告诉我您希望做出哪些改变，或者我们可以从头开始讨论您的学习目标。"
            self._add_to_history("assistant", response)
            return response
        else: # "unclear"
            print("[Orchestrator] User intent for plan confirmation is unclear.")
            response = "抱歉，我不太确定您的意思。我们是按这个计划开始，还是您想做一些调整呢？"
            self._add_to_history("assistant", response)
            return response

    def _generate_kb_and_start(self) -> str:
        print("[Orchestrator] Starting knowledge base generation...")
        
        topic_to_load = self.learning_blueprint.get("topic")
        if not topic_to_load:
            self.state = TutorState.ANALYZING_GOAL
            response = "错误：学习需求中没有找到有效的主题名称，我们重新开始吧。"
            self._add_to_history("assistant", response)
            return response

        max_retries = 2
        for attempt in range(max_retries):
            print(f"[Orchestrator] KB generation attempt {attempt + 1}/{max_retries} for topic '{topic_to_load}'...")
            
            prompt = f"""
            请根据这份最终的学习需求清单，为用户生成一份结构化的知识库。
            你的输出必须严格遵守定义的Pydantic模型格式。
            学习需求清单:
            ```json
            {json.dumps(self.learning_blueprint, ensure_ascii=False, indent=2)}
            ```
            用户上传的补充材料 (如果有的话，请优先使用这份材料中的内容):
            ---
            {self.uploaded_material or "无"}
            ---
            """
            # 使用结构化输出和Pydantic模型
            creator_response_obj = self.kb_creator_agent.step(
                BaseMessage.make_user_message("User", prompt),
            )

            kb_model = None
            # 结构化输出对象应该在第一个消息的`content`中
            if creator_response_obj and creator_response_obj.msgs:
                content = creator_response_obj.msgs[0].content
                if isinstance(content, KnowledgeBaseModel):
                    # 理想情况：直接Pydantic对象
                    kb_model = content
                    print("[Orchestrator] Received Pydantic object directly.")
                elif isinstance(content, str):
                    # 回退情况：字符串响应
                    try:
                        # 尝试1：直接解析整个字符串
                        kb_model = KnowledgeBaseModel.model_validate_json(content)
                        print("[Orchestrator] Successfully parsed the full string response.")
                    except Exception:
                        # 尝试2：从字符串中提取JSON块并解析它
                        print("[Orchestrator] Full string parsing failed. Attempting to extract JSON block...")
                        match = re.search(r'\{.*\}', content, re.DOTALL)
                        if match:
                            json_str = match.group(0)
                            try:
                                kb_model = KnowledgeBaseModel.model_validate_json(json_str)
                                print("[Orchestrator] Successfully extracted and parsed JSON block from string.")
                            except Exception as e:
                                print(f"[Orchestrator] Failed to parse extracted JSON block: {e}")
                                kb_model = None
                        else:
                            print("[Orchestrator] No JSON block found in string.")
                            kb_model = None
                    
            # --- 验证阶段 ---
            validation_passed = False
            if kb_model:
                # 2. 语义验证：检查是否覆盖所有子主题
                expected_topics = self.learning_blueprint.get("sub_topics", [])
                # 处理没有特定子主题的情况，任何概念都可以
                if not expected_topics:
                    if kb_model.concepts:
                        validation_passed = True
                        print("[Orchestrator] Syntactic validation passed (no specific sub-topics to check).")
                else:
                    generated_topics = list(kb_model.concepts.keys())
                    missing_topics = [topic for topic in expected_topics if topic not in generated_topics]

                    if not missing_topics:
                        validation_passed = True
                        print("[Orchestrator] KB data validated successfully (Syntactic & Semantic).")
                    else:
                        print(f"[Orchestrator] Semantic validation failed. Missing concepts for: {missing_topics}")
            else:
                response_type = type(creator_response_obj.msgs[0].content) if creator_response_obj and creator_response_obj.msgs else "None"
                print(f"[Orchestrator] KB generation failed: Could not obtain a valid Pydantic object. Got type: {response_type}")


            # --- 行动阶段 ---
            if validation_passed:
                # 现在，`kb_model` 是一个 Pydantic 对象，可以直接使用
                print(f"[Orchestrator] Generated KB for topic: '{topic_to_load}' with {len(kb_model.concepts)} concepts.")

                save_result = ""
                try:
                    # 将Pydantic模型直接传递给工具函数
                    save_result = save_knowledge_base(topic=topic_to_load, concepts=kb_model.concepts)
                    print(f"[Orchestrator] {save_result}")
                except Exception as e:
                    print(f"[Orchestrator] Error saving knowledge base: {e}")
                    # 如果保存失败，不应该继续
                    # 可以使用重试机制
                    if attempt < max_retries - 1:
                        continue
                    else:
                        error_message = f"抱歉，我在为您将知识库保存到文件时遇到了问题: {e}"
                        self._add_to_history("assistant", error_message)
                        self.state = TutorState.ANALYZING_GOAL
                        return error_message

                if "success" in save_result.lower():
                    # --- 重新加载知识库并开始辅导 ---
                    # 提取规范的主题名称以确保一致性
                    match = re.search(r"knowledge_bases[\\/]([^\\/]+\.json)", save_result)
                    if match:
                        actual_filename = match.group(1)
                        canonical_topic_name = actual_filename[:-5].replace('_', ' ').title()
                        
                        # 显式重新扫描和加载知识库
                        print(f"[Orchestrator] Reloading knowledge base to include '{canonical_topic_name}'...")
                        self.knowledge_base.scan_for_kbs()
                        loaded, reason = self.knowledge_base.load_kb_by_topic(canonical_topic_name)

                        if loaded:
                            print(f"[Orchestrator] KB for '{canonical_topic_name}' saved and reloaded successfully.")
                            # 现在加载了，可以直接开始会话
                            return self._start_tutoring_session_from_loaded_kb()
                        else:
                            # 这种情况不太可能，但以防万一，增加错误处理
                            print(f"[Orchestrator] Post-save validation/reload failed: {reason}")
                            error_message = f"抱歉，虽然知识库文件已创建，但在加载时失败了: {reason}。请稍后重试。"
                            self._add_to_history("assistant", error_message)
                            self.state = TutorState.ANALYZING_GOAL
                            return error_message
                    else:
                        print("[Orchestrator] Critical error: Could not parse filename from save result.")
                else:
                    print(f"[Orchestrator] Failed to save the generated KB: {save_result}")

            # 如果验证失败，回退到重试逻辑
            if attempt < max_retries - 1:
                print("[Orchestrator] Retrying KB generation...")
                continue
            else:
                error_message = "抱歉，我在为您创建知识库时遇到了问题。AI未能生成符合要求的、内容完整的数据。让我们回到规划阶段，重新定义一下学习目标也许会有帮助。"
                self._add_to_history("assistant", error_message)
                self.state = TutorState.ANALYZING_GOAL
                return error_message
        
        # 回退
        self.state = TutorState.ANALYZING_GOAL
        return "发生未知错误，知识库生成失败，请重试。"

    def _start_tutoring_session(self, topic_to_load: str) -> str:
        """Loads a knowledge base from a topic name and prepares the first question."""
        
        self.knowledge_base.scan_for_kbs()
        
        loaded, reason = self.knowledge_base.load_kb_by_topic(topic_to_load)
        if loaded:
            return self._start_tutoring_session_from_loaded_kb()
        else:
            self.state = TutorState.IDLE
            response = f"抱歉，加载知识库 '{topic_to_load}' 时失败了: {reason}。让我们重新开始吧。"
            self._add_to_history("assistant", response)
            return response

    def _start_tutoring_session_from_loaded_kb(self) -> str:
        """
        Starts the tutoring session assuming the knowledge base is already loaded.
        Prepares the first question for the user.
        """
        if not self.knowledge_base.is_loaded:
            self.state = TutorState.IDLE
            response = "错误：尝试在没有加载知识库的情况下开始教学。请先选择一个主题。"
            self._add_to_history("assistant", response)
            return response

        concept_keys = self.knowledge_base.get_concept_keys()
        if not concept_keys:
            self.state = TutorState.IDLE
            loaded_topic_name = self.knowledge_base.current_kb_name or "Unknown Topic"
            response = f"抱歉，虽然知识库 '{loaded_topic_name}' 已加载，但里面没有找到任何学习概念。AI可能未能成功生成内容，我们可以重新规划一下学习计划吗？"
            self._add_to_history("assistant", response)
            return response

        self.state = TutorState.TUTORING
        loaded_topic_name = self.knowledge_base.current_kb_name
        print(f"[Orchestrator] State changed to TUTORING. Starting session for topic: {loaded_topic_name}")
        
        # 找到第一个未掌握的概念
        next_action = self.analytical_planner.select_next_action(
            self.user_profile, self.knowledge_base, current_concept_id=None
        )
        
        if next_action["action"] == "finish":
            self.state = TutorState.IDLE
            response = f"恭喜你！根据记录，你已经掌握了 **{loaded_topic_name}** 的所有概念。"
            self._add_to_history("assistant", response)
            return response

        self.current_concept_id = next_action["concept_id"]
        concept = self.knowledge_base.get_concept(self.current_concept_id)

        if not concept:
            self.state = TutorState.IDLE
            response = f"抱歉，无法加载知识库 '{loaded_topic_name}' 中的概念 '{self.current_concept_id}'。文件可能已损坏，我们可以重新规划一下吗？"
            self._add_to_history("assistant", response)
            return response
            
        initial_question = concept.get('socratic_prompts', [f"你对'{self.current_concept_id}'有什么了解吗？"])[0]
        response = f"好的，我们开始学习 **{loaded_topic_name}**。让我们从第一个概念 **{self.current_concept_id}** 开始吧。\n\n{initial_question}"
        self._add_to_history("assistant", response)
        return response

    def _handle_tutoring(self, user_response: str) -> str:
        """
        The core tutoring loop. It now acts as an action dispatcher based on
        the decision from the pedagogical strategy agent.
        """
        self._add_to_history("user", user_response)

        # 1. 检查是否可以创建复习卡片
        card_notification = ""  # 用于存储制卡提示信息
        if len(self.history) >= 2:
            cards_created_count = self._check_and_trigger_flashcard_creation(
                conversation_snippet=self.history[-2:]
            )
            if cards_created_count > 0:
                if cards_created_count == 1:
                    card_notification = "💳 我已为你创建了1张复习卡片。\n\n"
                else:
                    card_notification = f"💳 我已将刚才的知识点分解，为你创建了 **{cards_created_count}** 张更易于记忆的原子化卡片。\n\n"
        
        # 2. 继续正常的教学流程，无论是否创建复习卡片
        current_concept_info = self.knowledge_base.get_concept(self.current_concept_id)
        if not current_concept_info:
            self.state = TutorState.IDLE
            return "错误：找不到当前概念，教学流程中断。"

        # 3. 构建完整的上下文，用于教学策略的决策
        context_for_strategist = {
            "user_message": user_response,
            "current_concept": {
                "name": self.current_concept_id,
                "difficulty": current_concept_info.get("difficulty", 3),
                "definition": current_concept_info.get("definition", ""),
            },
            "user_mastery_level": self.user_profile.knowledge_mastery.get(self.current_concept_id, 0.0),
            "conversation_history": [
                {"role": msg["role"], "content": msg["message"].content} 
                for msg in self.history
            ],
        }

        # 4. 调用'大脑'获取结构化决策
        try:
            strategy_response = self.strategy_agent.step(
                BaseMessage.make_user_message("user", json.dumps(context_for_strategist, ensure_ascii=False)),
            )
            self.strategy_agent.reset()

            decision = None
            if strategy_response and strategy_response.msgs:
                content = strategy_response.msgs[0].content
                if isinstance(content, FullPedagogicalDecisionModel):
                    decision = content
                elif isinstance(content, str):
                    # Robustness: Handle cases where the model returns a string anyway
                    parsed_json = parse_llm_json_output(content)
                    if parsed_json:
                        decision = FullPedagogicalDecisionModel.model_validate(parsed_json)
            
            if not decision:
                raise ValueError("Failed to get a valid decision from the strategy agent.")

        except Exception as e:
            print(f"[Orchestrator] Error getting pedagogical decision: {e}")
            # 关键失败回退
            response_text = "我好像有点困惑，我们能换个方式继续吗？"
            self._add_to_history("assistant", response_text)
            return response_text

        # 5. 执行决策，使用调度逻辑
        print(f"[Orchestrator] Strategy: {decision.response_strategy.value} | Action: {decision.action.action_type}")

        # 默认动作：只是说代理决定的内容
        response_text = decision.action.content
        
        # 调度器，用于需要状态改变的策略
        if decision.response_strategy == ResponseStrategy.FOLLOW_USER_LEAD:
            # Here you could add logic to parse the user's lead, e.g., topic switching.
            # For now, we just pass the message along.
            pass

        elif decision.response_strategy == ResponseStrategy.PROGRESS_TO_NEXT_CONCEPT:
           
            self.user_profile.knowledge_mastery[self.current_concept_id] = 1.0
            next_action_plan = self.analytical_planner.select_next_action(
                self.user_profile, self.knowledge_base, self.current_concept_id
            )
            if next_action_plan["action"] == "finish":
                self.state = TutorState.IDLE
                response_text = f"太棒了！我们完成了 **{self.knowledge_base.current_kb_name}** 的学习。"
            else:
                self.current_concept_id = next_action_plan["concept_id"]
                next_concept_info = self.knowledge_base.get_concept(self.current_concept_id)
                initial_question = next_concept_info.get('socratic_prompts', [""])[0]
                # 将代理的过渡文本与新概念的第一个问题结合起来
                response_text = f"{decision.action.content}\n\n让我们开始下一个概念：**{self.current_concept_id}**。{initial_question}"

        # 更新掌握程度，基于代理自己的分析
        if decision.response_strategy in [ResponseStrategy.REVIEW_AND_CLARIFY]:
             self.user_profile.knowledge_mastery[self.current_concept_id] = max(0, self.user_profile.knowledge_mastery.get(self.current_concept_id, 0.1) - 0.2)
        elif decision.response_strategy in [ResponseStrategy.CONSOLIDATE_AND_VERIFY, ResponseStrategy.SOCRATIC_GUIDANCE]:
             self.user_profile.knowledge_mastery[self.current_concept_id] = min(1.0, self.user_profile.knowledge_mastery.get(self.current_concept_id, 0.0) + 0.2)

        # 6. 将制卡提示与主要响应结合起来
        final_response = card_notification + response_text
        
        self._add_to_history("assistant", final_response)
        return final_response

    def _check_and_trigger_flashcard_creation(self, conversation_snippet: List[Dict[str, Any]]) -> int:
        """
        Checks a conversation snippet and creates flashcards if appropriate.
        Returns the number of cards created (0 if none).
        """
        if not conversation_snippet or len(conversation_snippet) < 2:
            return 0

        # Format history for the agents
        history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['message'].content}" for msg in conversation_snippet])
        
        # 1. 决定是否值得制作复习卡片
        try:
            # 最后一个消息是用户，倒数第二个消息是AI
            # 我们想要检查AI的解释是否被用户简单的确认
            # 是否值得制作复习卡片
            if "user" not in conversation_snippet[-1]['role'].lower():
                 return 0 # The last message must be from the user

            decision_response = self.flashcard_decision_agent.step(history_text)
            # 重要：重置代理的内存，确保每次检查都是独立的
            self.flashcard_decision_agent.reset() 
            if not decision_response or "YES" not in decision_response.msg.content.upper():
                return 0
        except Exception as e:
            print(f"[FlashcardCheck] Decision agent failed: {e}")
            return 0

        print("[FlashcardCheck] Decision: YES. Attempting to generate card.")

        # 2. 生成复习卡片内容
        try:
            generation_response = self.single_flashcard_agent.step(history_text)
            self.single_flashcard_agent.reset() 
            
            if not generation_response or not generation_response.msg.content:
                print("[FlashcardCheck] Generation agent returned no content.")
                return 0

            card_content_str = generation_response.msg.content
            
         
            # 如果存在markdown代码块，提取JSON
            match = re.search(r'\{.*\}', card_content_str, re.DOTALL)
            if match:
                card_content_str = match.group(0)
       

            # 解析响应以获取卡片数组
            response_data = json.loads(card_content_str)
            
            # 从响应中获取卡片列表
            card_list = response_data.get("cards", [])
            
            if not isinstance(card_list, list) or not card_list:
                print(f"[FlashcardCheck] Generation agent returned no valid card list: {card_content_str}")
                return 0
            
            # 跟踪成功创建了多少张卡片
            cards_created_count = 0
            concept_id = self.current_concept_id or "from_conversation"
            
            # 处理列表中的每张卡片
            for card_item in card_list:
                question = card_item.get("question")
                answer = card_item.get("answer")
                
                if question and answer:
                    try:
                        new_card = self.review_manager.add_card(
                            concept_id=concept_id,
                            question=question,
                            answer=answer
                        )
                        if new_card:
                            cards_created_count += 1
                            print(f"[FlashcardCheck] Created card: Q: {question[:50]}...")
                    except Exception as e:
                        # 如果单个卡片失败，记录但继续处理其他卡片
                        print(f"[FlashcardCheck] Failed to save a single card: {e}")
            
            if cards_created_count > 0:
                print(f"[FlashcardCheck] Successfully created and saved {cards_created_count} flashcard(s).")
                return cards_created_count
            else:
                print(f"[FlashcardCheck] No cards were ultimately created from the list.")
                return 0

        except json.JSONDecodeError as e:
            print(f"[FlashcardCheck] Failed to decode JSON from generation agent: {e}\nContent: '{card_content_str}'")
            return 0
        except Exception as e:
            print(f"[FlashcardCheck] Generation agent failed: {e}")
            return 0

    def _add_to_history(self, role: str, content: str):
        """Adds a message to the session's history."""
        if role.lower() == 'user':
            message = BaseMessage.make_user_message("user", content)
        else:
            message = BaseMessage.make_assistant_message("assistant", content)
        self.history.append({"role": role, "message": message}) 