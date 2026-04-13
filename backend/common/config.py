"""Backend configuration loading utilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"
CONFIG_PATH_ENV_VAR = "PAPER_WORKFLOW_CONFIG"
DOTENV_PATH_ENV_VAR = "PAPER_WORKFLOW_DOTENV_PATH"


class ConfigModel(BaseModel):
    """Base model for configuration sections."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AppSettings(ConfigModel):
    name: str = "paper-workflow"


class PathSettings(ConfigModel):
    data_dir: Path
    logs_dir: Path
    db_path: Path
    index_dir: Path
    pdf_dir: Path

    @property
    def ingest_logs_dir(self) -> Path:
        return self.logs_dir / "ingest"

    @property
    def retrieval_logs_dir(self) -> Path:
        return self.logs_dir / "retrieval"

    @property
    def traces_dir(self) -> Path:
        return self.logs_dir / "traces"


class ModelSettings(ConfigModel):
    embedding_model: str = "all-MiniLM-L6-v2"


class EmbeddingSettings(ConfigModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: int = 180

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


class LLMSettings(ConfigModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    timeout: int = 180
    query_rewrite_enabled: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


class LoggingSettings(ConfigModel):
    level: str = "INFO"
    json_output: bool = Field(default=True, alias="json")


class AppConfig(ConfigModel):
    app: AppSettings = Field(default_factory=AppSettings)
    paths: PathSettings
    models: ModelSettings = Field(default_factory=ModelSettings)
    embeddings: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def ensure_runtime_directories(self) -> None:
        """Create the runtime directories required by the backend."""

        directories = (
            self.paths.data_dir,
            self.paths.logs_dir,
            self.paths.db_path.parent,
            self.paths.index_dir,
            self.paths.pdf_dir,
            self.paths.ingest_logs_dir,
            self.paths.retrieval_logs_dir,
            self.paths.traces_dir,
        )

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


def resolve_config_path(
    config_path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the configuration file path, honoring the override env var."""

    environment = env or os.environ
    candidate = config_path or environment.get(CONFIG_PATH_ENV_VAR) or DEFAULT_CONFIG_PATH
    return Path(candidate).expanduser().resolve()


def load_settings(
    config_path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load backend settings from YAML, then apply environment overrides."""

    environment = _compose_environment(env)
    resolved_config_path = resolve_config_path(config_path, env=environment)
    raw_config = _load_config_file(resolved_config_path)
    _apply_environment_overrides(raw_config, environment)
    _resolve_path_settings(raw_config, _config_base_dir(resolved_config_path))
    return AppConfig.model_validate(raw_config)


def _load_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {config_path}")

    return loaded


def _config_base_dir(config_path: Path) -> Path:
    if config_path == DEFAULT_CONFIG_PATH:
        return PROJECT_ROOT
    return config_path.parent


def _apply_environment_overrides(raw_config: dict[str, Any], env: Mapping[str, str]) -> None:
    overrides: dict[tuple[str, str], tuple[str, Any]] = {
        ("app", "name"): ("PAPER_WORKFLOW_APP_NAME", str),
        ("paths", "data_dir"): ("PAPER_WORKFLOW_DATA_DIR", str),
        ("paths", "logs_dir"): ("PAPER_WORKFLOW_LOGS_DIR", str),
        ("paths", "db_path"): ("PAPER_WORKFLOW_DB_PATH", str),
        ("paths", "index_dir"): ("PAPER_WORKFLOW_INDEX_DIR", str),
        ("paths", "pdf_dir"): ("PAPER_WORKFLOW_PDF_DIR", str),
        ("models", "embedding_model"): ("PAPER_WORKFLOW_EMBEDDING_MODEL", str),
        ("embeddings", "api_key"): ("EMBEDDING_API_KEY", str),
        ("embeddings", "base_url"): ("EMBEDDING_BASE_URL", str),
        ("embeddings", "model"): ("EMBEDDING_MODEL", str),
        ("embeddings", "timeout"): ("EMBEDDING_TIMEOUT", int),
        ("llm", "api_key"): ("LLM_API_KEY", str),
        ("llm", "base_url"): ("LLM_BASE_URL", str),
        ("llm", "model"): ("LLM_MODEL", str),
        ("llm", "timeout"): ("LLM_TIMEOUT", int),
        ("llm", "query_rewrite_enabled"): ("PAPER_WORKFLOW_LLM_QUERY_REWRITE", _parse_bool),
        ("logging", "level"): ("PAPER_WORKFLOW_LOG_LEVEL", str),
        ("logging", "json"): ("PAPER_WORKFLOW_LOG_JSON", _parse_bool),
    }

    for (section, key), (env_var, parser) in overrides.items():
        value = env.get(env_var)
        if value is None:
            continue
        raw_config.setdefault(section, {})
        raw_config[section][key] = parser(value)


def _resolve_path_settings(raw_config: dict[str, Any], base_dir: Path) -> None:
    path_section = raw_config.setdefault("paths", {})

    for key in ("data_dir", "logs_dir", "db_path", "index_dir", "pdf_dir"):
        if key not in path_section:
            continue
        path_section[key] = _resolve_path(path_section[key], base_dir)


def _resolve_path(value: str | Path, base_dir: Path) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _compose_environment(env: Mapping[str, str] | None) -> dict[str, str]:
    explicit_env = dict(env) if env is not None else dict(os.environ)
    dotenv_vars = _load_dotenv_values(_resolve_dotenv_path(explicit_env))
    return {**dotenv_vars, **explicit_env}


def _resolve_dotenv_path(env: Mapping[str, str]) -> Path:
    raw_path = env.get(DOTENV_PATH_ENV_VAR)
    if raw_path:
        return Path(raw_path).expanduser().resolve()
    return (PROJECT_ROOT / ".env").resolve()


def _load_dotenv_values(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        values[key] = _strip_matching_quotes(raw_value.strip())

    return values


def _strip_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
