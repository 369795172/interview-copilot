import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "Interview Copilot"
    debug: bool = False

    data_dir: Path = Field(
        default=Path.home() / ".interview-copilot",
        description="Base directory for persistent data",
    )
    upload_dir: Optional[Path] = None

    # Database (SQLite for simplicity; swap to PostgreSQL via URL)
    database_url: str = "sqlite+aiosqlite:///./interview_copilot.db"

    # AI Builder Space – speech-to-text (fallback)
    ai_builder_token: Optional[str] = None
    ai_builder_base_url: str = "https://space.ai-builders.com/backend/v1"
    ai_builder_confidence_threshold: float = 0.4
    ai_builder_min_text_length: int = 3
    ai_builder_filter_relaxed: bool = False  # If True, use looser thresholds to reduce text loss
    ai_builder_prompt: str = (
        "这是一段技术面试对话录音。请只转写说话内容，不要描述噪音、设备状态或环境。"
        "规则：1) 保持原意，不回答或解释问题；2) 保留技术术语、产品名、框架名；"
        "3) 中英混说时保持原样；4) 修正明显的语音识别错误（如技术词拼写）；"
        "5) 去除口头禅（嗯、啊、那个等）；6) 使用中文标点。"
    )
    ai_builder_terms: str = (
        "React,Vue,Python,Java,JavaScript,TypeScript,Kubernetes,Docker,微服务,"
        "算法,数据结构,Redis,MySQL,PostgreSQL,API,REST,GraphQL,前端,后端"
    )

    # Volcano Engine BigModel ASR (primary, China-optimized)
    stt_provider: str = "auto"  # auto | volcengine | ai_builder
    volcengine_app_id: Optional[str] = None
    volcengine_asr_token: Optional[str] = None
    volc_session_rotate_sec: int = 480  # rotate VolcEngine session before ~10min limit; 0=disabled
    volcengine_hotwords: str = (
        "React,Vue,Python,Java,JavaScript,TypeScript,Kubernetes,Docker,微服务,"
        "算法,数据结构,Redis,MySQL,PostgreSQL,API,REST,GraphQL,前端,后端"
    )

    # LLM via OpenRouter (OpenAI-compatible)
    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-chat-v3-0324"
    llm_temperature: float = 0.4
    llm_max_tokens: int = 4096

    # LLM transcript refinement (post-STT correction)
    llm_refine_enabled: bool = False
    llm_refine_model: str = "openai/gpt-4o-mini"

    # Feishu
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_timeout: int = 30
    feishu_retry: int = 3

    # GitHub
    github_token: Optional[str] = None

    # ChromaDB
    chroma_persist_dir: Optional[Path] = None

    model_config = {
        "env_prefix": "IC_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def model_post_init(self, __context) -> None:
        if not self.llm_api_key:
            self.llm_api_key = os.getenv("OPENROUTER_LLM_API_KEY")
        if self.upload_dir is None:
            self.upload_dir = self.data_dir / "uploads"
        if self.chroma_persist_dir is None:
            self.chroma_persist_dir = self.data_dir / "chroma"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
