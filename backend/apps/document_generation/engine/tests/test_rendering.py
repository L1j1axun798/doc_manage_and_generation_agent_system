from __future__ import annotations

import base64
from io import BytesIO
from zipfile import ZipFile

import pytest
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt

from apps.document_generation.engine.contracts import (
    ConfirmedFact,
    GeneratedSection,
    GeneratedTable,
    RenderRequest,
    SourceLocator,
    TemplateDocument,
)
from apps.document_generation.engine.errors import (
    SourcePurposeMismatchError,
    TemplateInvalidError,
)
from apps.document_generation.engine.rendering import (
    DocxTemplateRenderer,
    infer_template_section_order,
)


def _template_bytes() -> bytes:
    document = Document()
    document.add_heading("{{ project_name }}四措两案", level=0)
    document.add_paragraph("计划数量：{{ planned_inspection_quantity }}台")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _facts() -> tuple[ConfirmedFact, ...]:
    locator = SourceLocator(paragraph_index=1)
    return (
        ConfirmedFact(
            field="project_name",
            value="示例风电场入场项目",
            value_type="string",
            source_document_version_id=1,
            locator=locator,
            confidence=1,
            confirmed_by=1,
        ),
        ConfirmedFact(
            field="planned_inspection_quantity",
            value=12,
            value_type="integer",
            source_document_version_id=1,
            locator=locator,
            confidence=1,
            confirmed_by=1,
        ),
    )


def test_template_preflight_and_render_produce_openable_docx() -> None:
    template = TemplateDocument(
        template_id="tpl-1",
        filename="四措两案模板.docx",
        content=_template_bytes(),
        required_placeholders=("project_name", "planned_inspection_quantity"),
    )
    renderer = DocxTemplateRenderer()

    preflight = renderer.preflight(
        template,
        {
            "project_name": "示例风电场入场项目",
            "planned_inspection_quantity": 12,
        },
    )
    artifact = renderer.render(
        RenderRequest(
            template=template,
            facts=_facts(),
            sections=(
                GeneratedSection(
                    section_code="safety_measures",
                    title="安全措施",
                    paragraphs=("入场前完成安全交底。",),
                    lists=(("核验人员资质", "核验安全带"),),
                    tables=(
                        GeneratedTable(
                            headers=("风险", "措施"),
                            rows=(("高处作业", "使用双钩安全带"),),
                        ),
                    ),
                ),
            ),
        )
    )

    assert preflight.valid is True
    assert set(preflight.declared_placeholders) == {
        "project_name",
        "planned_inspection_quantity",
    }
    rendered = Document(BytesIO(artifact.content))
    text = "\n".join(paragraph.text for paragraph in rendered.paragraphs)
    assert "示例风电场入场项目四措两案" in text
    assert "计划数量：12台" in text
    assert "安全措施" in text
    assert "入场前完成安全交底。" in text
    assert rendered.tables[-1].rows[0].cells[0].text == "风险"
    with ZipFile(BytesIO(artifact.content)) as archive:
        settings_xml = archive.read("word/settings.xml").decode()
        document_xml = archive.read("word/document.xml").decode()
    assert "w:updateFields" in settings_xml
    assert "{{" not in document_xml


def test_template_missing_required_placeholder_is_rejected() -> None:
    template = TemplateDocument(
        template_id="tpl-2",
        filename="四措两案模板.docx",
        content=_template_bytes(),
        required_placeholders=("project_name", "site_name"),
    )
    renderer = DocxTemplateRenderer()

    preflight = renderer.preflight(template, {"project_name": "项目"})

    assert preflight.valid is False
    assert set(preflight.missing_placeholders) == {
        "planned_inspection_quantity",
        "site_name",
    }
    with pytest.raises(TemplateInvalidError, match="模板预检失败"):
        renderer.render(
            RenderRequest(
                template=template,
                facts=_facts()[:1],
                sections=(),
            )
        )


def test_report_template_is_rejected() -> None:
    template = TemplateDocument(
        template_id="tpl-report",
        filename="检测报告模板.docx",
        content=_template_bytes(),
    )

    with pytest.raises(SourcePurposeMismatchError):
        DocxTemplateRenderer().preflight(template, {})


def test_filled_style_baseline_does_not_leak_historical_body_or_headers() -> None:
    historical = Document()
    cover = historical.add_paragraph()
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cover_run = cover.add_run("历史风电场项目四措两案")
    cover_run.font.size = Pt(22)
    body = historical.add_paragraph("历史甲方专有施工正文")
    body_run = body.runs[0]
    body_run.font.size = Pt(16)
    body_run._element.get_or_add_rPr().get_or_add_rFonts().set(
        qn("w:eastAsia"),
        "仿宋_GB2312",
    )
    historical.add_picture(
        BytesIO(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
                "ASsJTYQAAAAASUVORK5CYII="
            )
        )
    )
    historical.sections[0].header.paragraphs[0].text = "历史甲方页眉"
    historical.sections[0].footer.paragraphs[0].text = "历史项目页脚"
    appendix = historical.add_section(WD_SECTION.NEW_PAGE)
    appendix.orientation = WD_ORIENT.LANDSCAPE
    appendix.page_width, appendix.page_height = (
        appendix.page_height,
        appendix.page_width,
    )
    output = BytesIO()
    historical.save(output)
    template = TemplateDocument(
        template_id="tpl-style-only",
        filename="已批准样式基线.docx",
        content=output.getvalue(),
    )
    renderer = DocxTemplateRenderer()

    preflight = renderer.preflight(
        template,
        {
            "project_name": "当前风电场入场项目",
            "client_name": "当前委托方",
        },
    )
    current_project_fact = _facts()[0].model_copy(update={"value": "当前风电场入场项目"})
    client_fact = current_project_fact.model_copy(
        update={
            "field": "client_name",
            "value": "当前委托方",
        }
    )
    artifact = renderer.render(
        RenderRequest(
            template=template,
            facts=(current_project_fact, client_fact),
            sections=(
                GeneratedSection(
                    section_code="overview",
                    title="工程概况",
                    paragraphs=("当前项目计划开展入场检测。",),
                ),
            ),
        )
    )

    assert preflight.valid is True
    assert preflight.declared_placeholders == ()
    assert preflight.warnings
    rendered = Document(BytesIO(artifact.content))
    visible_text = "\n".join(
        [
            *(paragraph.text for paragraph in rendered.paragraphs),
            *(
                paragraph.text
                for section in rendered.sections
                for paragraph in (*section.header.paragraphs, *section.footer.paragraphs)
            ),
        ]
    )
    assert "当前风电场入场项目" in visible_text
    assert "当前委托方" in visible_text
    assert "当前项目计划开展入场检测" in visible_text
    assert "历史风电场" not in visible_text
    assert "历史甲方" not in visible_text
    assert "历史项目" not in visible_text
    assert rendered.sections[0].orientation == WD_ORIENT.PORTRAIT
    generated_body = next(
        paragraph
        for paragraph in rendered.paragraphs
        if "当前项目计划开展入场检测" in paragraph.text
    )
    assert generated_body.runs[0].font.size == Pt(16)
    assert (
        generated_body.runs[0]._element.get_or_add_rPr().get_or_add_rFonts().get(qn("w:eastAsia"))
        == "仿宋_GB2312"
    )
    assert generated_body.paragraph_format.first_line_indent == Pt(32)
    with ZipFile(BytesIO(artifact.content)) as archive:
        assert not any(name.startswith("word/media/") for name in archive.namelist())


def test_style_only_baseline_without_english_list_or_table_styles_still_renders() -> None:
    baseline = Document()
    for style_name in ("List Bullet", "Table Grid"):
        style = baseline.styles[style_name]
        style._element.getparent().remove(style._element)
    output = BytesIO()
    baseline.save(output)
    template = TemplateDocument(
        template_id="tpl-minimal-styles",
        filename="客户四措两案样式基线.docx",
        content=output.getvalue(),
    )

    artifact = DocxTemplateRenderer().render(
        RenderRequest(
            template=template,
            facts=_facts()[:1],
            sections=(
                GeneratedSection(
                    section_code="safety_measures",
                    title="安全措施",
                    lists=(("核验人员资质",),),
                    tables=(
                        GeneratedTable(
                            headers=("风险", "措施"),
                            rows=(("高处作业", "使用双钩安全带"),),
                        ),
                    ),
                ),
            ),
        )
    )

    rendered = Document(BytesIO(artifact.content))
    assert "• 核验人员资质" in [paragraph.text for paragraph in rendered.paragraphs]
    assert rendered.tables[-1].rows[1].cells[1].text == "使用双钩安全带"


def test_customer_outline_controls_section_order_and_keeps_existing_heading_format() -> None:
    baseline = Document()
    baseline.add_paragraph("甲方封面标题")
    baseline.add_paragraph("第一章、项目简介")
    baseline.add_paragraph("历史项目概况")
    baseline.add_paragraph("第二章、安全措施")
    baseline.add_paragraph("历史安全正文")
    baseline.add_paragraph("第三章、施工方案")
    baseline.add_paragraph("历史施工正文")
    for style_name in ("Heading 2", "Heading 3"):
        style = baseline.styles[style_name]
        style._element.getparent().remove(style._element)
    output = BytesIO()
    baseline.save(output)

    assert infer_template_section_order(output.getvalue()) == (
        "overview",
        "safety_measures",
        "construction_plan",
    )

    artifact = DocxTemplateRenderer().render(
        RenderRequest(
            template=TemplateDocument(
                template_id="customer-outline",
                filename="甲方四措两案.docx",
                content=output.getvalue(),
            ),
            facts=_facts()[:1],
            sections=(
                GeneratedSection(
                    section_code="overview",
                    title="系统概况标题",
                    paragraphs=("当前项目概况",),
                ),
                GeneratedSection(
                    section_code="safety_measures",
                    title="系统安全标题",
                    paragraphs=("当前安全正文",),
                ),
                GeneratedSection(
                    section_code="construction_plan",
                    title="系统施工标题",
                    paragraphs=("当前施工正文",),
                ),
            ),
        )
    )

    rendered = Document(BytesIO(artifact.content))
    texts = [paragraph.text for paragraph in rendered.paragraphs if paragraph.text.strip()]
    assert texts == [
        "甲方封面标题",
        "第一章、项目简介",
        "当前项目概况",
        "第二章、安全措施",
        "当前安全正文",
        "第三章、施工方案",
        "当前施工正文",
    ]
    assert "历史项目概况" not in texts
    assert "系统概况标题" not in texts
