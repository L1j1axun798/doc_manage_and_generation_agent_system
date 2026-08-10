from __future__ import annotations

import json
from hashlib import sha256
from io import BytesIO
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from common.storage import LocalDocumentStorage

from .exceptions import DocumentGenerationError
from .models import (
    ApprovalStatus,
    ApprovedDocumentIllustration,
    GenerationTask,
    GenerationTaskAsset,
)

AMAP_ROOT = "https://restapi.amap.com"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MIN_RENDER_WIDTH_PX = 1200


def illustration_is_applicable(
    illustration: ApprovedDocumentIllustration,
    task: GenerationTask,
) -> bool:
    rules = illustration.applicability if isinstance(illustration.applicability, dict) else {}
    facts = {
        str(item.get("field")): item.get("value")
        for item in (task.facts_snapshot or [])
        if isinstance(item, dict) and item.get("field")
    }
    risks = set((task.risk_profile or {}).get("risk_codes", []))
    allowed_risks = {str(value) for value in rules.get("risk_codes", [])}
    if allowed_risks and not risks.intersection(allowed_risks):
        return False
    allowed_models = {str(value) for value in rules.get("turbine_models", [])}
    if allowed_models and str(facts.get("turbine_model") or "") not in allowed_models:
        return False
    allowed_methods = {str(value) for value in rules.get("method_codes", [])}
    current_methods = {
        str(value) for value in facts.get("inspection_method_codes", [])
    } if isinstance(facts.get("inspection_method_codes"), list) else set()
    if allowed_methods and not current_methods.intersection(allowed_methods):
        return False
    required_equipment = {str(value) for value in rules.get("required_equipment", [])}
    current_equipment = {
        str(value) for value in facts.get("rescue_equipment", [])
    } if isinstance(facts.get("rescue_equipment"), list) else set()
    return not required_equipment or required_equipment.issubset(current_equipment)


def normalize_document_image(content: bytes) -> tuple[bytes, str, int, int]:
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise DocumentGenerationError("IMAGE_INVALID", "图片为空或超过20 MB")
    try:
        with Image.open(BytesIO(content)) as source:
            source.load()
            if source.format not in {"PNG", "JPEG"}:
                raise DocumentGenerationError("IMAGE_INVALID", "仅支持PNG或JPEG图片")
            image = source.convert("RGBA" if source.mode in {"RGBA", "LA"} else "RGB")
            width, height = image.size
            if width < MIN_RENDER_WIDTH_PX:
                raise DocumentGenerationError(
                    "IMAGE_RESOLUTION_INSUFFICIENT",
                    "图片宽度不足1200像素，无法保证A4版面约200 DPI的清晰度",
                )
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
    except UnidentifiedImageError as exc:
        raise DocumentGenerationError("IMAGE_INVALID", "图片文件损坏或格式无法识别") from exc
    return output.getvalue(), "image/png", width, height


def _save_task_asset(
    *,
    task: GenerationTask,
    actor: object,
    kind: str,
    content: bytes,
    caption: str,
    alt_text: str,
    metadata: dict[str, object],
    approved_illustration: ApprovedDocumentIllustration | None = None,
    storage: LocalDocumentStorage | None = None,
) -> GenerationTaskAsset:
    normalized, media_type, width, height = normalize_document_image(content)
    backend = storage or LocalDocumentStorage()
    stored = backend.save_uploaded_file(
        SimpleUploadedFile(f"{kind}.png", normalized, content_type=media_type)
    )
    old_path = ""
    with transaction.atomic():
        existing = GenerationTaskAsset.objects.select_for_update().filter(
            task=task,
            kind=kind,
        ).first()
        if existing is not None:
            old_path = existing.storage_path
        asset, _created = GenerationTaskAsset.objects.update_or_create(
            task=task,
            kind=kind,
            defaults={
                "approved_illustration": approved_illustration,
                "storage_path": stored.relative_path,
                "filename": f"{kind}.png",
                "media_type": media_type,
                "sha256": stored.sha256,
                "width_px": width,
                "height_px": height,
                "caption": caption,
                "alt_text": alt_text,
                "metadata": metadata,
                "confirmed_by": actor,
                "confirmed_at": timezone.now(),
            },
        )
    if old_path and old_path != stored.relative_path:
        backend.delete(old_path)
    return asset


def select_approved_illustration(
    *,
    task: GenerationTask,
    actor: object,
    illustration_id: int,
    storage: LocalDocumentStorage | None = None,
) -> GenerationTaskAsset:
    illustration = ApprovedDocumentIllustration.objects.filter(
        pk=illustration_id,
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
    ).select_related("document_version").first()
    if illustration is None:
        raise DocumentGenerationError("ILLUSTRATION_UNAVAILABLE", "所选图片未审核或已停用")
    if illustration.kind not in {
        ApprovedDocumentIllustration.Kind.HEIGHT_ESCAPE_PLAN,
        ApprovedDocumentIllustration.Kind.HEIGHT_RESCUE_PLAN,
    }:
        raise DocumentGenerationError("ILLUSTRATION_UNAVAILABLE", "图片类型不适用于高空预案")
    risks = set((task.risk_profile or {}).get("risk_codes", []))
    if "high_altitude" not in risks and "climbing_tower" not in risks:
        raise DocumentGenerationError("ILLUSTRATION_NOT_APPLICABLE", "当前任务不包含高处作业风险")
    if not illustration_is_applicable(illustration, task):
        raise DocumentGenerationError(
            "ILLUSTRATION_NOT_APPLICABLE",
            "审核图片与当前机型、作业方式或救援装备不匹配",
        )
    backend = storage or LocalDocumentStorage()
    path = backend.resolve(illustration.document_version.storage_path)
    if not path.is_file():
        raise DocumentGenerationError("ILLUSTRATION_UNAVAILABLE", "审核图片物理文件不存在")
    content = path.read_bytes()
    if sha256(content).hexdigest() != illustration.document_version.sha256:
        raise DocumentGenerationError("ILLUSTRATION_INTEGRITY_FAILED", "审核图片哈希校验失败")
    return _save_task_asset(
        task=task,
        actor=actor,
        kind=illustration.kind,
        content=content,
        caption=illustration.caption,
        alt_text=illustration.alt_text,
        metadata={
            "illustration_id": illustration.pk,
            "applicability": illustration.applicability,
            "source_sha256": illustration.document_version.sha256,
        },
        approved_illustration=illustration,
        storage=backend,
    )


def _amap_json(path: str, params: dict[str, object]) -> dict[str, object]:
    key = str(getattr(settings, "AMAP_WEB_SERVICE_KEY", "")).strip()
    if not key:
        raise DocumentGenerationError(
            "MAP_PROVIDER_UNAVAILABLE",
            "服务端未配置高德Web服务Key，暂不能查询救援路线",
            status_code=503,
        )
    query = urlencode({**params, "key": key})
    timeout = int(getattr(settings, "AMAP_WEB_SERVICE_TIMEOUT_SECONDS", 10))
    try:
        with urlopen(f"{AMAP_ROOT}{path}?{query}", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise DocumentGenerationError(
            "MAP_PROVIDER_FAILED",
            "高德路线服务暂时不可用，请稍后重试",
            status_code=502,
        ) from exc
    if payload.get("status") != "1":
        raise DocumentGenerationError(
            "MAP_PROVIDER_FAILED",
            f"高德路线服务返回失败：{payload.get('info') or 'unknown'}",
            status_code=502,
        )
    return payload


def _driving_route(origin: str, destination: str) -> dict[str, object]:
    payload = _amap_json(
        "/v3/direction/driving",
        {"origin": origin, "destination": destination, "extensions": "base"},
    )
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    paths = route.get("paths") if isinstance(route, dict) else []
    if not isinstance(paths, list) or not paths or not isinstance(paths[0], dict):
        raise DocumentGenerationError("ROUTE_NOT_FOUND", "未查询到可用驾车路线")
    path = paths[0]
    polylines: list[str] = []
    for step in path.get("steps", []):
        if isinstance(step, dict) and isinstance(step.get("polyline"), str):
            polylines.append(step["polyline"])
    return {
        "distance_m": int(path.get("distance") or 0),
        "duration_s": int(path.get("duration") or 0),
        "polyline": ";".join(polylines),
    }


def search_hospital_routes(*, origin: str) -> list[dict[str, object]]:
    payload = _amap_json(
        "/v3/place/around",
        {
            "location": origin,
            "keywords": "医院",
            "radius": 50000,
            "sortrule": "distance",
            "offset": 8,
            "page": 1,
            "extensions": "base",
        },
    )
    pois = payload.get("pois") if isinstance(payload.get("pois"), list) else []
    candidates: list[dict[str, object]] = []
    for poi in pois[:8]:
        if not isinstance(poi, dict) or not poi.get("location") or not poi.get("name"):
            continue
        route = _driving_route(origin, str(poi["location"]))
        candidates.append(
            {
                "hospital_id": str(poi.get("id") or ""),
                "hospital_name": str(poi["name"]),
                "address": str(poi.get("address") or ""),
                "location": str(poi["location"]),
                **route,
            }
        )
    return sorted(candidates, key=lambda value: int(value["duration_s"]))[:5]


def confirm_rescue_route(
    *,
    task: GenerationTask,
    actor: object,
    origin: str,
    hospital_name: str,
    hospital_location: str,
    storage: LocalDocumentStorage | None = None,
) -> GenerationTaskAsset:
    route = _driving_route(origin, hospital_location)
    polyline = str(route["polyline"])
    if not polyline:
        raise DocumentGenerationError("ROUTE_NOT_FOUND", "路线缺少可绘制轨迹")
    key = str(getattr(settings, "AMAP_WEB_SERVICE_KEY", "")).strip()
    query = urlencode(
        {
            "key": key,
            "size": "1024*768",
            "scale": 2,
            "markers": f"mid,0xFF0000,A:{origin}|mid,0x00AA00,B:{hospital_location}",
            "paths": f"10,0x0066FF,1,,0.8:{polyline}",
        }
    )
    timeout = int(getattr(settings, "AMAP_WEB_SERVICE_TIMEOUT_SECONDS", 10))
    try:
        with urlopen(f"{AMAP_ROOT}/v3/staticmap?{query}", timeout=timeout) as response:
            content = response.read()
    except Exception as exc:
        raise DocumentGenerationError(
            "MAP_PROVIDER_FAILED", "救援路线图生成失败", status_code=502
        ) from exc
    query_time = timezone.now().isoformat()
    frozen_route = {
        "origin": origin,
        "hospital_name": hospital_name,
        "hospital_location": hospital_location,
        "distance_m": route["distance_m"],
        "duration_s": route["duration_s"],
        "query_time": query_time,
        "route_data_sha256": sha256(
            json.dumps(route, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    return _save_task_asset(
        task=task,
        actor=actor,
        kind=GenerationTaskAsset.Kind.RESCUE_ROUTE,
        content=content,
        caption=(
            f"救援路线：风场至{hospital_name}（约{round(int(route['distance_m']) / 1000, 1)}公里，"
            f"预计{max(1, round(int(route['duration_s']) / 60))}分钟）"
        ),
        alt_text=f"风场至{hospital_name}的驾车救援路线图",
        metadata=frozen_route,
        storage=storage,
    )
