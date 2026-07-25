from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
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

    source_section = source_document.sections[-1]
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
    document.add_heading(project_name.strip(), level=0)
    document.add_paragraph("入场四措两案")
    client_name = context.get("client_name")
    if isinstance(client_name, str) and client_name.strip():
        document.add_paragraph(f"委托方：{client_name.strip()}")
    document.add_page_break()
    return document


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

        for section in request.sections:
            document.add_heading(section.title, level=1)
            for paragraph in section.paragraphs:
                document.add_paragraph(paragraph)
            for items in section.lists:
                for item in items:
                    document.add_paragraph(item, style="List Bullet")
            for generated_table in section.tables:
                table = document.add_table(
                    rows=1,
                    cols=len(generated_table.headers),
                    style="Table Grid",
                )
                for index, header in enumerate(generated_table.headers):
                    table.rows[0].cells[index].text = header
                for row in generated_table.rows:
                    cells = table.add_row().cells
                    for index, value in enumerate(row):
                        cells[index].text = value

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
