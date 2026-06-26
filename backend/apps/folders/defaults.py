from dataclasses import dataclass


@dataclass(frozen=True)
class StandardFolderDefinition:
    code: str
    name: str
    sort_order: int
    aliases: tuple[str, ...] = ()

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


STANDARD_PUBLIC_ROOTS = [
    StandardFolderDefinition(
        code="PUBLIC-COMPLETION",
        name="竣工档案资料",
        sort_order=1,
        aliases=(
            "完工资料档案",
            "完工资料",
            "档案资料",
            "项目过程资料",
            "过程资料",
            "检测报告",
            "其他附件",
        ),
    ),
    StandardFolderDefinition(code="PUBLIC-COMPANY", name="公司资质", sort_order=2),
    StandardFolderDefinition(code="PUBLIC-STAFF", name="人员资质", sort_order=3),
    StandardFolderDefinition(
        code="PUBLIC-TOOLS",
        name="工具及年检资质",
        sort_order=4,
        aliases=("工器具年检资质",),
    ),
    StandardFolderDefinition(
        code="PUBLIC-INSTRUMENT",
        name="仪器仪表设备年检资质",
        sort_order=5,
        aliases=("仪器设备年检资质",),
    ),
    StandardFolderDefinition(
        code="PUBLIC-VEHICLE",
        name="车辆年检资质",
        sort_order=6,
        aliases=("车辆年检及资质",),
    ),
    StandardFolderDefinition(
        code="PUBLIC-PROTECTION",
        name="个人防护用品",
        sort_order=7,
        aliases=("劳动防护用品资料", "劳动防护用品"),
    ),
]

ARCHIVE_ROOT = StandardFolderDefinition(
    code="PUBLIC-ARCHIVE",
    name="归档资料",
    sort_order=99,
)

LEGACY_PROJECT_FOLDER_NAMES = frozenset(
    {
        "项目过程资料",
        "过程资料",
        "检测报告",
        "其他附件",
    }
)


def standard_root_for_name(folder_name: str) -> StandardFolderDefinition | None:
    for definition in STANDARD_PUBLIC_ROOTS:
        if folder_name in definition.names:
            return definition
    return None


def standard_root_for_code(folder_code: str) -> StandardFolderDefinition | None:
    for definition in STANDARD_PUBLIC_ROOTS:
        if folder_code == definition.code:
            return definition
    return None
