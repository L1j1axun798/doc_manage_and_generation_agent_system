from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.text.font import CT_RPr
from docx.shared import Pt
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from docxtpl import DocxTemplate
from jinja2 import Environment, StrictUndefined

from .contracts import (
    RenderedArtifact,
    RenderRequest,
    TemplateDocument,
    TemplateValidationResult,
)
from .errors import SourcePurposeMismatchError, TemplateInvalidError
from .parsing import REPORT_FILENAME_MARKERS

PLACEHOLDER_RE = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*}}")
STYLE_ONLY_TEMPLATE_WARNING = "模板不含占位符，将仅继承样式并清除历史正文和页眉页脚"
SECTION_NUMBER_PREFIXES = ("一", "二", "三", "四", "五", "六", "七", "八")
SUBHEADING_RE = re.compile(r"^(?:[（(][一二三四五六七八九十]+[）)]|[一二三四五六七八九十]+、)")


def _docx_xml_text(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as archive:
            return "\n".join(
                archive.read(name).decode("utf-8", errors="ignore")
                for name in archive.namelist()
                if name.startswith("word/") and name.endswith(".xml")
            )
    except BadZipFile as exc:
        raise TemplateInvalidError("模板不是有效的DOCX文件") from exc


def _ensure_entry_template(template: TemplateDocument) -> None:
    if any(marker in template.filename for marker in REPORT_FILENAME_MARKERS):
        raise SourcePurposeMismatchError("报告模板不能用于入场四措两案")


def _prepare_style_only_baseline(
    source_document: DocumentObject,
    context: Mapping[str, object],
) -> DocumentObject:
    document = Document()
    document.part._styles_part._element = deepcopy(source_document.part._styles_part._element)
    document.part.numbering_part._element = deepcopy(source_document.part.numbering_part._element)

    # Historical baselines may end with a landscape appendix. The first section is
    # the approved cover/body baseline; copying the last section made every newly
    # generated entry plan landscape.
    source_section = source_document.sections[0]
    target_section = document.sections[0]
    for attribute in (
        "page_height",
        "page_width",
        "orientation",
        "top_margin",
        "bottom_margin",
        "left_margin",
        "right_margin",
        "gutter",
        "header_distance",
        "footer_distance",
    ):
        setattr(target_section, attribute, getattr(source_section, attribute))

    project_name = context.get("project_name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise TemplateInvalidError("样式基线渲染必须提供项目名称")
    cover_run_properties = _cover_run_properties(source_document)
    _add_cover_line(document, project_name.strip(), cover_run_properties)
    _add_cover_line(document, "入场四措两案", cover_run_properties)
    client_name = context.get("client_name")
    if isinstance(client_name, str) and client_name.strip():
        _add_cover_line(
            document,
            f"委托方：{client_name.strip()}",
            _dominant_body_run_properties(source_document),
        )
    document.add_page_break()
    return document


def _cover_run_properties(source_document: DocumentObject) -> CT_RPr | None:
    for paragraph in source_document.paragraphs:
        if paragraph.text.strip() and paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            for run in paragraph.runs:
                if run.text.strip() and run._r.rPr is not None:
                    return deepcopy(run._r.rPr)
    return None


def _dominant_body_run_properties(
    source_document: DocumentObject,
) -> CT_RPr | None:
    weights: Counter[str] = Counter()
    properties: dict[str, CT_RPr] = {}
    for paragraph in source_document.paragraphs:
        style_name = paragraph.style.name.lower() if paragraph.style is not None else ""
        if (
            not paragraph.text.strip()
            or paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER
            or style_name.startswith(("heading", "title", "toc"))
        ):
            continue
        for run in paragraph.runs:
            text = run.text.strip()
            if not text or run._r.rPr is None:
                continue
            key = str(run._r.rPr.xml)
            weights[key] += len(text)
            properties.setdefault(key, deepcopy(run._r.rPr))
    if not weights:
        return None
    return properties[weights.most_common(1)[0][0]]


def _heading_run_properties(source_document: DocumentObject) -> CT_RPr | None:
    for paragraph in source_document.paragraphs:
        style_name = paragraph.style.name.lower() if paragraph.style is not None else ""
        if not style_name.startswith("heading"):
            continue
        for run in paragraph.runs:
            if run.text.strip() and run._r.rPr is not None:
                return deepcopy(run._r.rPr)
    return None


def _apply_run_properties(run: Run, properties: CT_RPr | None) -> None:
    if properties is None:
        return
    run_element = run._r
    if run_element.rPr is not None:
        run_element.remove(run_element.rPr)
    run_element.insert(0, deepcopy(properties))


def _add_cover_line(
    document: DocumentObject,
    text: str,
    run_properties: CT_RPr | None,
) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(text)
    _apply_run_properties(run, run_properties)


def _apply_body_format(
    paragraph: Paragraph,
    run_properties: CT_RPr | None,
    *,
    first_line_indent: bool,
) -> None:
    for run in paragraph.runs:
        _apply_run_properties(run, run_properties)
    paragraph_format = paragraph.paragraph_format
    paragraph_format.space_after = Pt(0)
    paragraph_format.line_spacing = 1.5
    if first_line_indent:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        sizes = [run.font.size.pt for run in paragraph.runs if run.font.size is not None]
        paragraph_format.first_line_indent = Pt(2 * (sizes[0] if sizes else 12))


def _has_style(document: DocumentObject, style_name: str) -> bool:
    return any(style.name == style_name for style in document.styles)


def _add_list_item(document: DocumentObject, text: str) -> Paragraph:
    # Some approved customer baselines intentionally contain only the styles used
    # by their historical body.  Requiring Word's English built-in style name
    # makes those otherwise valid templates fail late in the rendering stage.
    if _has_style(document, "List Bullet"):
        return document.add_paragraph(text, style="List Bullet")
    return document.add_paragraph(f"• {text}")


def _add_generated_table(
    document: DocumentObject,
    *,
    rows: int,
    cols: int,
) -> Table:
    table = document.add_table(rows=rows, cols=cols)
    if _has_style(document, "Table Grid"):
        table.style = "Table Grid"
    return table


class DocxTemplateRenderer:
    _media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def preflight(
        self,
        template: TemplateDocument,
        available_context: Mapping[str, object] | None = None,
    ) -> TemplateValidationResult:
        _ensure_entry_template(template)
        if Path(template.filename).suffix.lower() != ".docx":
            return TemplateValidationResult(
                valid=False,
                missing_placeholders=template.required_placeholders,
                warnings=("模板必须为DOCX格式",),
            )
        try:
            docx_template = DocxTemplate(BytesIO(template.content))
            declared = set(docx_template.get_undeclared_template_variables())
        except Exception:
            return TemplateValidationResult(
                valid=False,
                missing_placeholders=template.required_placeholders,
                warnings=("模板无法解析",),
            )
        xml_text = _docx_xml_text(template.content)
        declared.update(PLACEHOLDER_RE.findall(xml_text))
        required = set(template.required_placeholders)
        missing_in_template = required - declared
        context_fields = set((available_context or {}).keys())
        missing_context = declared - context_fields if available_context is not None else set()
        missing = missing_in_template | missing_context
        return TemplateValidationResult(
            valid=not missing,
            declared_placeholders=tuple(sorted(declared)),
            missing_placeholders=tuple(sorted(missing)),
            warnings=(STYLE_ONLY_TEMPLATE_WARNING,) if not declared else (),
        )

    def render(self, request: RenderRequest) -> RenderedArtifact:
        context = {fact.field: fact.value for fact in request.facts}
        validation = self.preflight(request.template, context)
        if not validation.valid:
            missing = "、".join(validation.missing_placeholders)
            raise TemplateInvalidError(f"模板预检失败，缺少字段或占位符：{missing}")

        try:
            if not validation.declared_placeholders:
                source_document = Document(BytesIO(request.template.content))
                document = _prepare_style_only_baseline(source_document, context)
            else:
                template = DocxTemplate(BytesIO(request.template.content))
                environment = Environment(
                    autoescape=True,
                    undefined=StrictUndefined,
                )
                template.render(context, jinja_env=environment)
                rendered_buffer = BytesIO()
                template.save(rendered_buffer)
                rendered_buffer.seek(0)
                document = Document(rendered_buffer)
        except Exception as exc:
            if isinstance(exc, TemplateInvalidError):
                raise
            raise TemplateInvalidError("模板渲染失败") from exc

        body_run_properties = (
            _dominant_body_run_properties(source_document)
            if not validation.declared_placeholders
            else None
        )
        heading_run_properties = (
            _heading_run_properties(source_document)
            if not validation.declared_placeholders
            else None
        )
        for section_index, section in enumerate(request.sections):
            prefix = (
                SECTION_NUMBER_PREFIXES[section_index]
                if section_index < len(SECTION_NUMBER_PREFIXES)
                else str(section_index + 1)
            )
            heading = document.add_heading(f"{prefix}、{section.title}", level=2)
            for run in heading.runs:
                _apply_run_properties(run, heading_run_properties)
            for paragraph in section.paragraphs:
                is_subheading = bool(SUBHEADING_RE.match(paragraph.strip()))
                rendered_paragraph = (
                    document.add_heading(paragraph, level=3)
                    if is_subheading
                    else document.add_paragraph(paragraph)
                )
                _apply_body_format(
                    rendered_paragraph,
                    body_run_properties,
                    first_line_indent=not is_subheading,
                )
            for items in section.lists:
                for item in items:
                    rendered_item = _add_list_item(document, item)
                    _apply_body_format(
                        rendered_item,
                        body_run_properties,
                        first_line_indent=False,
                    )
            for generated_table in section.tables:
                table = _add_generated_table(
                    document,
                    rows=1,
                    cols=len(generated_table.headers),
                )
                for index, header in enumerate(generated_table.headers):
                    table.rows[0].cells[index].text = header
                    _apply_body_format(
                        table.rows[0].cells[index].paragraphs[0],
                        body_run_properties,
                        first_line_indent=False,
                    )
                for row in generated_table.rows:
                    cells = table.add_row().cells
                    for index, value in enumerate(row):
                        cells[index].text = value
                        _apply_body_format(
                            cells[index].paragraphs[0],
                            body_run_properties,
                            first_line_indent=False,
                        )

        update_fields = OxmlElement("w:updateFields")
        update_fields.set(qn("w:val"), "true")
        document.settings.element.append(update_fields)
        output = BytesIO()
        document.save(output)
        content = output.getvalue()
        xml_text = _docx_xml_text(content)
        if "{{" in xml_text or "{%" in xml_text:
            raise TemplateInvalidError("渲染结果仍包含模板占位符")

        output_name = Path(request.template.filename).stem + "-generated.docx"
        return RenderedArtifact(
            filename=output_name,
            media_type=self._media_type,
            content=content,
            sha256=sha256(content).hexdigest(),
        )
