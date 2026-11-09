from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "speakfill"
    app_base_url: str = "http://localhost:8080"
    data_dir: str = "/data"
    database_url: str = "postgresql+psycopg://speakfill:speakfill@db:5432/speakfill"

    # smallest.ai voice APIs ("stub" = offline placeholder audio for tests)
    voice_provider: str = "smallest"
    smallest_api_key: str = ""
    smallest_stt_model: str = "pulse"  # multilingual STT (NOT pulse-pro: English-only)
    smallest_tts_model: str = "lightning_v3.1_pro"
    smallest_voice_en: str = "meher"
    smallest_voice_hi: str = "meher"  # verify a Hindi-suitable voice during live key test

    # LLM provider behind a thin adapter ("stub" = scripted responses for tests)
    llm_provider: str = "stub"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""  # empty = provider default (OpenAI); set for OpenAI-compatible hosts


settings = Settings()
