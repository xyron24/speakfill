"""Filled-PDF rendering: Jinja HTML template -> WeasyPrint -> /data/pdfs/<id>.pdf."""

from __future__ import annotations

import pathlib
import uuid
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.config import settings
from app.services.review import SOURCE_LABELS

TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent.parent / "pdf"
_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


def pdfs_dir() -> pathlib.Path:
    d = pathlib.Path(settings.data_dir) / "pdfs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _display(field_row: dict) -> str:
    if field_row["readable"]:
        return str(field_row["readable"])
    if field_row["value"] is None:
        return "—"
    return str(field_row["value"])


def render_pdf(
    submission_id: uuid.UUID,
    review: dict,
    completed_at: datetime,
    consent_ts: str | None,
) -> pathlib.Path:
    language = review["language"]
    fields = []
    for r in review["fields"]:
        source = r["source"] or "typed"
        fields.append({
            "label": r["label"],
            "display": _display(r),
            "source": source,
            "source_label": SOURCE_LABELS.get(source, {}).get(language, source.title()),
        })

    consent_row = next((r for r in review["fields"] if r["key"] == "consent"), None)
    agreed = consent_row is not None and consent_row["value"] is True
    if language == "hi":
        declaration = "मैं पुष्टि करता/करती हूँ कि दी गई जानकारी सत्य है।"
        consent_text = f"सहमत ({consent_ts})" if agreed else "असहमत"
    else:
        declaration = "I confirm that the information I have given is true."
        consent_text = f"Agreed ({consent_ts})" if agreed else "Declined"

    html = _env.get_template("form_filled.html").render(
        language=language,
        submission_id=str(submission_id),
        completed_at=completed_at.strftime("%Y-%m-%d %H:%M"),
        template_name=review["template"]["name"].get(language, review["template"]["id"]),
        template_version=review["template"]["version"],
        fields=fields,
        declaration_text=declaration,
        consent_text=consent_text,
        verify_url=f"{settings.app_base_url}/api/submissions/{submission_id}.pdf",
    )
    out = pdfs_dir() / f"{submission_id}.pdf"
    HTML(string=html).write_pdf(str(out))
    return out
