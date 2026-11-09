from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Template, TemplateField
from app.schemas import TemplateDetail, TemplateFieldFile, TemplateSummary

router = APIRouter(prefix="/api", tags=["templates"])


@router.get("/templates", response_model=list[TemplateSummary])
def list_templates(db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(Template, func.count(TemplateField.id))
            .outerjoin(TemplateField, TemplateField.template_id == Template.id)
            .where(Template.is_active.is_(True))
            .group_by(Template.id)
        ).all()
    )
    return [
        TemplateSummary(id=t.id, name=t.name, version=t.version, field_count=n) for t, n in rows
    ]


@router.get("/templates/{template_id}", response_model=TemplateDetail)
def get_template(template_id: str, db: Session = Depends(get_db)):
    tpl = db.get(Template, template_id)
    if tpl is None or not tpl.is_active:
        raise HTTPException(status_code=404, detail=f"unknown template: {template_id}")
    fields = (
        db.execute(
            select(TemplateField)
            .where(TemplateField.template_id == template_id)
            .order_by(TemplateField.ord)
        )
        .scalars()
        .all()
    )
    return TemplateDetail(
        id=tpl.id,
        name=tpl.name,
        version=tpl.version,
        fields=[
            TemplateFieldFile(
                key=f.field_key,
                ord=f.ord,
                type=f.ftype,
                required=f.required,
                validation=f.validation,
                options=f.options,
                prompts=f.prompts,
            )
            for f in fields
        ],
    )
