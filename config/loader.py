import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

class TaxonomyTheme(BaseModel):
    id: str
    name: str
    keywords: List[str] = Field(default_factory=list)

class AppSettings(BaseModel):
    name: str = "Groww Review Pulse AI"
    version: str = "0.1.0"
    target_package_id: str = "com.nextbillion.groww"
    target_country: str = "in"
    target_language: str = "en"

class IngestionSettings(BaseModel):
    default_lookback_weeks: int = 8
    min_lookback_weeks: int = 8
    max_lookback_weeks: int = 12
    max_reviews: int = 1000
    batch_size: int = 200

class SanitizationSettings(BaseModel):
    min_review_words: int = 8
    strip_emojis: bool = True
    filter_one_word_reviews: bool = True
    redact_pii: bool = True

class ThemingSettings(BaseModel):
    max_themes: int = 5
    top_themes_in_pulse: int = 3
    taxonomy: List[TaxonomyTheme] = Field(default_factory=list)

class LLMPhaseConfig(BaseModel):
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.2
    rpm_limit: int = 30

class LLMSettings(BaseModel):
    phase2: LLMPhaseConfig = Field(default_factory=lambda: LLMPhaseConfig(provider="groq", model="llama-3.3-70b-versatile", rpm_limit=30))
    phase3: LLMPhaseConfig = Field(default_factory=lambda: LLMPhaseConfig(provider="gemini", model="gemini-2.5-flash", rpm_limit=15))

class PulseSettings(BaseModel):
    max_words: int = 250
    required_verbatim_quotes: int = 3
    required_action_ideas: int = 3

class MCPSettings(BaseModel):
    enable_fallback_local_export: bool = True
    docs_title_prefix: str = "Groww Weekly Review Pulse"
    gmail_subject_prefix: str = "[Weekly Pulse] Groww User Feedback & Action Items"

class AppConfig(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    sanitization: SanitizationSettings = Field(default_factory=SanitizationSettings)
    theming: ThemingSettings = Field(default_factory=ThemingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    pulse: PulseSettings = Field(default_factory=PulseSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)

    # Runtime Environment Overrides & API Keys
    groq_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    gemini_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    openai_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    output_dir: str = Field(default_factory=lambda: os.getenv("OUTPUT_DIR", "./output"))
    default_email_recipient: str = Field(default_factory=lambda: os.getenv("DEFAULT_EMAIL_RECIPIENT", "user@example.com"))

_config_instance: Optional[AppConfig] = None

def get_settings(config_path: Optional[str] = None) -> AppConfig:
    global _config_instance
    if _config_instance is not None and config_path is None:
        return _config_instance

    if config_path is None:
        base_dir = Path(__file__).resolve().parent.parent
        config_path = str(base_dir / "config" / "settings.yaml")

    yaml_data: Dict[str, Any] = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}

    _config_instance = AppConfig(**yaml_data)
    return _config_instance
