from apps.document_generation.revision import (
    is_revision_followup,
    revision_required_literals,
)


def test_revision_required_literals_extracts_personnel_names_and_long_numbers() -> None:
    instruction = "在合适位置加入人员信息：张三，123456789012345；李四，321654987123456。"

    assert revision_required_literals(instruction) == (
        "张三",
        "123456789012345",
        "李四",
        "321654987123456",
    )


def test_revision_followup_recognizes_unapplied_feedback() -> None:
    assert is_revision_followup("没有看到你在正文内容中的修改。") is True
    assert is_revision_followup("补充岗位职责和记录要求。") is False
