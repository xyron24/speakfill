"""Pydantic schemas: template file validation + API responses."""

from typing import Literal

from pydantic import BaseModel, Field

FieldType = Literal["text", "date", "choice", "phone", "email", "number", "longtext", "boolean"]
Locale = Literal["en", "hi"]


class FieldPrompt(BaseModel):
    ask: str
    hint: str = ""


class TemplateFieldFile(BaseModel):
    """One field inside templates_v1.json (also the API shape)."""

    key: str
    ord: int
    type: FieldType
    required: bool = True
    validation: dict | None = None
    options: list[dict] | None = None
    prompts: dict[Locale, FieldPrompt]


class TemplateFile(BaseModel):
    """Validates templates_v1.json at seed time (acceptance criterion #3)."""

    id: str
    name: dict[str, str]
    version: int = 1
    fields: list[TemplateFieldFile] = Field(min_length=1)


class TemplateSummary(BaseModel):
    id: str
    name: dict[str, str]
    version: int
    field_count: int


class TemplateDetail(BaseModel):
    id: str
    name: dict[str, str]
    version: int
    fields: list[TemplateFieldFile]
