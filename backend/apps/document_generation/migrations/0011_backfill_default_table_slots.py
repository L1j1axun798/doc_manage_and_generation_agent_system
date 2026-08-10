from django.db import migrations


APPROVED_DEFAULT_TABLE_STYLE = "approved_default_v1"


def _default_slots(section_codes):
    sections = set(section_codes or [])
    slots = []

    def add(block_key, section_code, headers=None):
        if section_code not in sections:
            return
        slot = {
            "block_key": block_key,
            "section_code": section_code,
            "anchor": "section_end",
            "style_source": APPROVED_DEFAULT_TABLE_STYLE,
        }
        if headers:
            slot["headers"] = headers
            slot["column_count"] = len(headers)
        slots.append(slot)

    add(
        "personnel_information",
        "organization_measures",
        ["序号", "姓名", "岗位/职务", "联系电话", "证书及有效期"],
    )
    risk_section = (
        "risk_identification" if "risk_identification" in sections else "safety_measures"
    )
    add("hazard_controls", risk_section)
    add("work_process_points", "construction_plan")
    add("inspection_tools", "technical_measures")
    add("safety_equipment", "safety_measures")
    add("ppe_items", "safety_measures")
    return slots


def backfill_tableless_template_slots(apps, schema_editor):
    DocumentTemplate = apps.get_model("document_generation", "DocumentTemplate")
    for template in DocumentTemplate.objects.iterator():
        schema = dict(template.layout_schema or {})
        if schema.get("table_slots"):
            continue
        slots = _default_slots(template.section_order)
        if not slots:
            continue
        schema.update(
            {
                "version": 2,
                "uses_approved_default_table_style": True,
                "table_slots": slots,
            }
        )
        template.layout_schema = schema
        template.save(update_fields=["layout_schema"])


class Migration(migrations.Migration):
    dependencies = [("document_generation", "0010_documenttemplate_layout_schema_and_more")]

    operations = [
        migrations.RunPython(backfill_tableless_template_slots, migrations.RunPython.noop),
    ]
