from __future__ import annotations

from typing import Any

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from .exceptions import DocumentAgentDisabled, DocumentAgentPhase5Blocked
from .models import DocumentTemplate, GenerationTask
from .permissions import IsDocumentGenerationUser
from .selectors import (
    available_templates,
    visible_generation_tasks,
    writable_project_for_user,
)
from .serializers import (
    DocumentTemplateSerializer,
    ExportSerializer,
    GeneratedSectionSerializer,
    GeneratedSectionUpdateSerializer,
    GenerationFactConfirmSerializer,
    GenerationPipelineCreateSerializer,
    GenerationSourceAddSerializer,
    GenerationTaskCreateSerializer,
    GenerationTaskSerializer,
    GenerationTraceEventSerializer,
    ReviewActionSerializer,
    SectionLockSerializer,
    TraceEventQuerySerializer,
)
from .services import (
    add_generation_sources,
    approve_generation_task,
    confirm_and_request_generation,
    confirm_generation_facts,
    create_generation_task,
    edit_generated_section,
    export_generation_task,
    lock_all_valid_sections,
    prepare_fact_confirmation,
    request_generation,
    request_section_regeneration,
    retry_generation_task,
    set_section_lock,
    start_compilation_pipeline,
    submit_generation_review,
)


class DocumentAgentFeatureMixin:
    def initial(self, request: Any, *args: Any, **kwargs: Any) -> None:
        if not getattr(settings, "DOCUMENT_AGENT_ENABLED", False):
            raise DocumentAgentDisabled
        if not getattr(settings, "DOCUMENT_AGENT_PHASE5_APPROVED", False):
            raise DocumentAgentPhase5Blocked
        return super().initial(request, *args, **kwargs)  # type: ignore[misc]


class DocumentTemplateViewSet(
    DocumentAgentFeatureMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DocumentTemplate.objects.none()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [IsDocumentGenerationUser]
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DocumentTemplate.objects.none()
        return available_templates()


class GenerationTaskViewSet(
    DocumentAgentFeatureMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = GenerationTask.objects.none()
    serializer_class = GenerationTaskSerializer
    permission_classes = [IsDocumentGenerationUser]
    filterset_fields = ["project", "status"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return GenerationTask.objects.none()
        return visible_generation_tasks(self.request.user)

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_serializer_class(self):
        return {
            "create": GenerationTaskCreateSerializer,
            "pipeline": GenerationPipelineCreateSerializer,
            "sources": GenerationSourceAddSerializer,
            "confirm_facts": GenerationFactConfirmSerializer,
            "confirm_and_generate": GenerationFactConfirmSerializer,
            "update_section": GeneratedSectionUpdateSerializer,
            "lock_section": SectionLockSerializer,
            "submit_review": ReviewActionSerializer,
            "approve": ReviewActionSerializer,
            "export": ExportSerializer,
        }.get(self.action, GenerationTaskSerializer)

    @extend_schema(
        request=GenerationPipelineCreateSerializer,
        responses=GenerationTaskSerializer,
    )
    @action(detail=False, methods=["post"], url_path="pipeline")
    def pipeline(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = writable_project_for_user(request.user, data["project_id"])
        if project is None:
            return Response(
                {"detail": "项目不存在或当前用户无权编制入场资料"},
                status=status.HTTP_404_NOT_FOUND,
            )
        template = get_object_or_404(available_templates(), pk=data["template_id"])
        task, created = start_compilation_pipeline(
            actor=request.user,
            project=project,
            template=template,
            document_version_ids=data["document_version_ids"],
            document_purpose=data["document_purpose"],
            business_type=data["business_type"],
            idempotency_key=data["idempotency_key"],
            initial_facts=data["facts"],
            request=request,
        )
        return Response(
            GenerationTaskSerializer(task, context=self.get_serializer_context()).data,
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        request=GenerationTaskCreateSerializer,
        responses=GenerationTaskSerializer,
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project = writable_project_for_user(request.user, data["project_id"])
        if project is None:
            return Response(
                {"detail": "项目不存在或当前用户无权编制入场资料"},
                status=status.HTTP_404_NOT_FOUND,
            )
        template = get_object_or_404(available_templates(), pk=data["template_id"])
        task, created = create_generation_task(
            actor=request.user,
            project=project,
            template=template,
            document_purpose=data["document_purpose"],
            business_type=data["business_type"],
            idempotency_key=data["idempotency_key"],
            initial_facts=data["facts"],
            request=request,
        )
        return Response(
            GenerationTaskSerializer(task, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        request=GenerationSourceAddSerializer,
        responses=GenerationTaskSerializer,
    )
    @action(detail=True, methods=["post"])
    def sources(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = add_generation_sources(
            actor=request.user,
            task=self.get_object(),
            document_version_ids=serializer.validated_data["document_version_ids"],
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data)

    @extend_schema(request=None, responses=GenerationTaskSerializer)
    @action(detail=True, methods=["post"])
    def extract(self, request, pk=None):
        task = prepare_fact_confirmation(
            actor=request.user,
            task=self.get_object(),
            request=request,
        )
        return Response(
            GenerationTaskSerializer(task).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        request=GenerationFactConfirmSerializer,
        responses=GenerationTaskSerializer,
    )
    @action(detail=True, methods=["put"], url_path="facts/confirm")
    def confirm_facts(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = confirm_generation_facts(
            actor=request.user,
            task=self.get_object(),
            facts=serializer.validated_data["facts"],
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data)

    @extend_schema(
        request=GenerationFactConfirmSerializer,
        responses=GenerationTaskSerializer,
    )
    @action(detail=True, methods=["put"], url_path="facts/confirm-and-generate")
    def confirm_and_generate(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = confirm_and_request_generation(
            actor=request.user,
            task=self.get_object(),
            facts=serializer.validated_data["facts"],
            request=request,
        )
        return Response(
            GenerationTaskSerializer(task).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(request=None, responses=GenerationTaskSerializer)
    @action(detail=True, methods=["post"], url_path="sections/lock-all")
    def lock_all_sections(self, request, pk=None):
        task = lock_all_valid_sections(
            actor=request.user,
            task=self.get_object(),
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data)

    @extend_schema(
        parameters=[TraceEventQuerySerializer],
        responses=GenerationTraceEventSerializer(many=True),
    )
    @action(detail=True, methods=["get"], url_path="events")
    def events(self, request, pk=None):
        task = self.get_object()
        query = TraceEventQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = task.workflow_events.filter(
            sequence__gt=query.validated_data["after_sequence"]
        ).order_by("sequence")[:200]
        return Response(GenerationTraceEventSerializer(rows, many=True).data)

    @extend_schema(request=None, responses=GenerationTaskSerializer)
    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        task = request_generation(
            actor=request.user,
            task=self.get_object(),
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(request=None, responses=GenerationTaskSerializer)
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        task = retry_generation_task(
            actor=request.user,
            task=self.get_object(),
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        request=ReviewActionSerializer,
        responses=GenerationTaskSerializer,
        methods=["POST"],
    )
    @action(detail=True, methods=["post"], url_path="submit-review")
    def submit_review(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = submit_generation_review(
            actor=request.user,
            task=self.get_object(),
            comment=serializer.validated_data["comment"],
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data)

    @extend_schema(
        request=ReviewActionSerializer,
        responses=GenerationTaskSerializer,
    )
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = approve_generation_task(
            actor=request.user,
            task=self.get_object(),
            comment=serializer.validated_data["comment"],
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data)

    @extend_schema(request=ExportSerializer, responses=GenerationTaskSerializer)
    @action(detail=True, methods=["post"])
    def export(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = export_generation_task(
            actor=request.user,
            task=self.get_object(),
            idempotency_key=serializer.validated_data["idempotency_key"],
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data)

    def update_section(self, request, pk=None, section_code=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = edit_generated_section(
            actor=request.user,
            task=self.get_object(),
            section_code=section_code,
            content=serializer.validated_data["content"],
            expected_revision=serializer.validated_data["expected_revision"],
            request=request,
        )
        return Response(GeneratedSectionSerializer(section).data)

    def lock_section(self, request, pk=None, section_code=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = set_section_lock(
            actor=request.user,
            task=self.get_object(),
            section_code=section_code,
            locked=serializer.validated_data["locked"],
            request=request,
        )
        return Response(GeneratedSectionSerializer(section).data)

    def regenerate_section(self, request, pk=None, section_code=None):
        task = request_section_regeneration(
            actor=request.user,
            task=self.get_object(),
            section_code=section_code,
            request=request,
        )
        return Response(GenerationTaskSerializer(task).data, status=status.HTTP_202_ACCEPTED)
