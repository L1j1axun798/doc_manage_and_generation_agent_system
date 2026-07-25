from rest_framework.exceptions import APIException


class DocumentGenerationError(APIException):
    status_code = 400
    default_code = "document_generation_error"
    default_detail = "入场资料编制操作失败"

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        status_code: int | None = None,
    ) -> None:
        self.default_code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=detail, code=code)


class DocumentAgentDisabled(DocumentGenerationError):
    def __init__(self) -> None:
        super().__init__(
            "DOCUMENT_AGENT_DISABLED",
            "入场资料编制功能尚未启用",
            status_code=404,
        )


class DocumentAgentPhase5Blocked(DocumentGenerationError):
    def __init__(self) -> None:
        super().__init__(
            "PHASE5_GATE_NOT_APPROVED",
            "入场资料编制尚未通过真实模型和技术负责人验收",
            status_code=503,
        )
