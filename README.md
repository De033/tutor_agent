# 智能AI助教 (Intelligent Tutor Agent)

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Streamlit-red.svg)](https://streamlit.io/)
[![License](https.img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

<div align="center">

**一个能将复杂对话无缝转化为高效记忆卡片的智能学习伙伴。**<br>
*让知识不再被遗忘。*


</div>

---

在学习新知识时，我们常常面临"听懂了，但记不住"的困境。**智能AI助教**直面这一挑战，它不仅是一个知识渊博的导师，更是一个能将您与AI的深度对话，在后台自动、无感地转化为高质量原子化闪卡（Flashcards）的智能系统。

## ✨ 核心功能

- **无缝制卡体验**: 您只管沉浸学习，系统会在最合适的时机，自动将知识点转化为卡片，不打断您的学习流。
- **高质量原子化卡片**: 采用 **概念/描述框架** 提示工程，确保生成的每一张卡片都聚焦于一个独立的知识点，极大提升记忆效率。
- **动态知识库**: 支持通过对话或直接上传文档（PDF/Markdown）来创建和扩展您的专属知识库。
- **多智能体架构**: 先进的模块化设计，确保系统响应迅速、逻辑清晰，且易于未来扩展。

## 🚀 快速上手 (Quick Start)

三步即可在本地运行您的AI助教。

### 1. 安装依赖
```bash
git clone https://github.com/your-username/tutor-agent.git
cd tutor-agent
pip install -r requirements.txt
```

### 2. 配置密钥
-   在项目根目录 (`tutor_agent/`) 下，将 `.env.example` 文件复制一份并重命名为 `.env`。
-   打开新建的 `.env` 文件，填入您的模型服务提供商的API密钥和API地址。
    ```env
    # .env
    OPENAI_COMPATIBLE_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    OPENAI_COMPATIBLE_API_BASE="https://api.your-provider.com/v1"
    ```
-   **重要**: `.env` 文件包含了您的私人密钥，请确保不要将它提交到任何版本控制系统（如Git）。

### 3. 运行Web应用
```bash
streamlit run run_webapp.py
```
---

## 核心技术与依赖库 (Core Technologies & Libraries)

本项目能够实现，离不开以下优秀的开源项目和学术理念。在此向它们的开发者和研究者表示诚挚的感谢。

*   **[Streamlit](https://streamlit.io/)**: 用于快速构建和部署数据驱动的交互式 Web 应用界面。
*   **[Camel (Communicative Agents for "Mind" Exploration of Large Language Model)](https://github.com/camel-ai/camel)**: 作为驱动多智能体（Multi-Agent）协作、对话和工具使用的核心框架。
*   **[Pydantic](https://docs.pydantic.dev/)**: 用于强制大型语言模型（LLM）生成结构化的、可验证的 JSON 输出，是确保数据一致性的关键。
*   **[FSRS (Free Spaced Repetition Scheduler)](https://github.com/open-spaced-repetition/fsrs-rs)**: 作为项目间隔重复记忆机制的设计蓝本和理论基础，指导了我们对记忆卡片复习功能的设计与规划。
*   **[OpenAI Python Library](https://github.com/openai/openai-python)**: 用于与底层的大型语言模型 API (如 GPT-4) 进行稳定、高效的通信。

完整的依赖列表请参见 `requirements.txt` 文件。
