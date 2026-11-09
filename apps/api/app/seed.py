"""Idempotent seed: inserts scholarship-v1 template + fields iff missing/same version.

Run inside the api container:  python -m app.seed
"""

import json
import pathlib

from app.db import SessionLocal
from app.models import Template, TemplateField
from app.schemas import TemplateFile

DATA_PATH = pathlib.Path(__file__).with_name("data") / "templates_v1.json"


def seed() -> str:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    tpl = TemplateFile.model_validate(raw)  # acceptance criterion #3: strict validation

    with SessionLocal() as db:
        existing = db.get(Template, tpl.id)
        if existing is not None and existing.version == tpl.version:
            return f"already seeded: {tpl.id} v{tpl.version} (no-op)"

        if existing is None:
            db.add(Template(id=tpl.id, name=tpl.name, version=tpl.version, is_active=True))
        else:
            existing.name = tpl.name
            existing.version = tpl.version
            # Replace fields wholesale on version bump.
            for row in db.query(TemplateField).filter_by(template_id=tpl.id).all():
                db.delete(row)

        for f in tpl.fields:
            db.add(
                TemplateField(
                    template_id=tpl.id,
                    field_key=f.key,
                    ord=f.ord,
                    ftype=f.type,
                    required=f.required,
                    validation=f.validation,
                    options=f.options,
                    prompts={loc: p.model_dump() for loc, p in f.prompts.items()},
                )
            )
        db.commit()
        return f"seeded: {tpl.id} v{tpl.version} ({len(tpl.fields)} fields)"


if __name__ == "__main__":
    print(seed())
