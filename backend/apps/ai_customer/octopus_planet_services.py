import hashlib
import math
import time

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.ai_customer.models import OctopusNote, OctopusPlanetPublish, OctopusPlanetTagStat


VECTOR_SIZE = 32


class OctopusPlanetError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalize_tag(value: str) -> str:
    tag = "".join(str(value or "").split())
    max_length = int(getattr(settings, "OCTOPUS_PLANET_MAX_TAG_LENGTH", 10) or 10)
    if not tag:
        raise OctopusPlanetError("标签不能为空")
    if len(tag) > max_length:
        raise OctopusPlanetError(f"标签最多 {max_length} 个字")
    return tag.lower()


def display_tag(value: str) -> str:
    return "".join(str(value or "").split())[: int(getattr(settings, "OCTOPUS_PLANET_MAX_TAG_LENGTH", 10) or 10)]


def _hash_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def embedding_text(tag: str) -> list[float]:
    text = f"标签：{normalize_tag(tag)}"
    vector = [0.0 for _ in range(VECTOR_SIZE)]
    tokens = list(text) + [text[i : i + 2] for i in range(max(len(text) - 1, 0))]
    for index, token in enumerate(tokens):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        slot = digest[0] % VECTOR_SIZE
        sign = 1 if digest[1] % 2 == 0 else -1
        vector[slot] += sign * (1.0 if index < len(text) else 0.65)
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / norm for item in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(item * item for item in left[:size])) or 1.0
    right_norm = math.sqrt(sum(item * item for item in right[:size])) or 1.0
    return dot / (left_norm * right_norm)


def particle_color(tag: str) -> str:
    hue = _hash_int(tag) % 360
    chroma = 0.72
    light = 0.58
    x = chroma * (1 - abs((hue / 60) % 2 - 1))
    if hue < 60:
        r, g, b = chroma, x, 0
    elif hue < 120:
        r, g, b = x, chroma, 0
    elif hue < 180:
        r, g, b = 0, chroma, x
    elif hue < 240:
        r, g, b = 0, x, chroma
    elif hue < 300:
        r, g, b = x, 0, chroma
    else:
        r, g, b = chroma, 0, x
    m = light - chroma / 2
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, round((r + m) * 255))),
        max(0, min(255, round((g + m) * 255))),
        max(0, min(255, round((b + m) * 255))),
    )


def project_vector(vector: list[float], point_id: str = "") -> tuple[float, float, float]:
    if not vector:
        vector = embedding_text(point_id or "octopus")
    x = sum(value * math.sin((index + 1) * 1.73) for index, value in enumerate(vector))
    y = sum(value * math.cos((index + 1) * 2.11) for index, value in enumerate(vector))
    z = sum(value * math.sin((index + 1) * 0.91 + 1.7) for index, value in enumerate(vector))
    norm = math.sqrt(x * x + y * y + z * z) or 1.0
    jitter_seed = _hash_int(point_id or "planet")
    jitter = ((jitter_seed % 1000) / 1000 - 0.5) * 0.08
    radius = 0.86 + jitter
    return (x / norm * radius, y / norm * radius, z / norm * radius)


def _qdrant_client():
    url = str(getattr(settings, "QDRANT_URL", "") or "").strip()
    if not url:
        return None
    from qdrant_client import QdrantClient

    return QdrantClient(url=url, api_key=getattr(settings, "QDRANT_API_KEY", None))


def ensure_qdrant_collection(vector_size: int):
    client = _qdrant_client()
    if not client:
        return False
    collection = getattr(settings, "QDRANT_COLLECTION", "octopus_planet_notes")
    vector_name = getattr(settings, "QDRANT_VECTOR_NAME", "tag_vector")
    try:
        from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

        exists = client.collection_exists(collection)
        if not exists:
            client.create_collection(
                collection_name=collection,
                vectors_config={vector_name: VectorParams(size=vector_size, distance=Distance.COSINE)},
            )
        for field_name, schema in {
            "user_id": PayloadSchemaType.INTEGER,
            "is_public": PayloadSchemaType.BOOL,
            "tag_normalized": PayloadSchemaType.KEYWORD,
            "published_at": PayloadSchemaType.INTEGER,
        }.items():
            try:
                client.create_payload_index(collection_name=collection, field_name=field_name, field_schema=schema)
            except Exception:
                pass
        return True
    except Exception:
        return False


def upsert_qdrant_publish(publish: OctopusPlanetPublish) -> bool:
    client = _qdrant_client()
    if not client or not publish.tag_vector:
        return False
    collection = getattr(settings, "QDRANT_COLLECTION", "octopus_planet_notes")
    vector_name = getattr(settings, "QDRANT_VECTOR_NAME", "tag_vector")
    try:
        from qdrant_client.models import PointStruct

        ensure_qdrant_collection(len(publish.tag_vector))
        client.upsert(
            collection_name=collection,
            points=[
                PointStruct(
                    id=int(publish.qdrant_point_id),
                    vector={vector_name: publish.tag_vector},
                    payload={
                        "publish_id": publish.id,
                        "notebook_id": publish.note_id,
                        "user_id": publish.user_id,
                        "tag": publish.tag,
                        "tag_normalized": publish.tag_normalized,
                        "is_public": publish.is_public,
                        "published_at": int(publish.published_at.timestamp()) if publish.published_at else int(time.time()),
                    },
                )
            ],
        )
        return True
    except Exception:
        return False


def qdrant_search(query_vector: list[float], scope: str, user, limit: int):
    client = _qdrant_client()
    if not client:
        return None
    collection = getattr(settings, "QDRANT_COLLECTION", "octopus_planet_notes")
    vector_name = getattr(settings, "QDRANT_VECTOR_NAME", "tag_vector")
    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        must = [
            FieldCondition(key="is_public", match=MatchValue(value=True)),
        ]
        if scope == "mine":
            must.append(FieldCondition(key="user_id", match=MatchValue(value=user.id)))
        hits = client.search(
            collection_name=collection,
            query_vector=(vector_name, query_vector),
            query_filter=Filter(must=must),
            limit=limit,
        )
        return {
            int(hit.payload.get("publish_id")): float(hit.score)
            for hit in hits
            if hit.payload and hit.payload.get("publish_id")
        }
    except Exception:
        return None


def publish_note(user, note_id: int, tag_value: str) -> OctopusPlanetPublish:
    note = OctopusNote.objects.filter(id=note_id, user=user).first()
    if not note:
        raise OctopusPlanetError("记事本不存在", 404)
    normalized = normalize_tag(tag_value)
    tag = display_tag(tag_value)
    vector = embedding_text(normalized)
    defaults = {
        "user": user,
        "tag": tag,
        "tag_normalized": normalized,
        "is_public": True,
        "tag_vector": vector,
        "particle_color": particle_color(normalized),
        "particle_size": 1.0,
        "qdrant_point_id": str(note.id),
    }
    publish, _ = OctopusPlanetPublish.objects.update_or_create(note=note, defaults=defaults)
    x, y, z = project_vector(vector, publish.qdrant_point_id)
    publish.particle_x = x
    publish.particle_y = y
    publish.particle_z = z
    publish.is_vector_ready = upsert_qdrant_publish(publish)
    publish.save(
        update_fields=[
            "user",
            "tag",
            "tag_normalized",
            "is_public",
            "tag_vector",
            "particle_x",
            "particle_y",
            "particle_z",
            "particle_color",
            "particle_size",
            "qdrant_point_id",
            "is_vector_ready",
            "updated_at",
        ]
    )
    stat, created = OctopusPlanetTagStat.objects.get_or_create(
        user=user,
        tag_normalized=normalized,
        defaults={"tag": tag, "use_count": 0},
    )
    stat.tag = tag
    stat.use_count = F("use_count") + 1
    stat.last_used_at = timezone.now()
    stat.save(update_fields=["tag", "use_count", "last_used_at"])
    stat.refresh_from_db()
    return publish


def common_tags(user):
    limit = int(getattr(settings, "OCTOPUS_PLANET_COMMON_TAG_LIMIT", 5) or 5)
    stats = OctopusPlanetTagStat.objects.filter(user=user).order_by("-use_count", "-last_used_at")[:limit]
    return [{"tag": item.tag, "use_count": item.use_count} for item in stats]


def publish_queryset(scope: str, user):
    qs = OctopusPlanetPublish.objects.select_related("note", "user").filter(is_public=True)
    if scope == "mine":
        qs = qs.filter(user=user)
    return qs


def serialize_particle(publish: OctopusPlanetPublish, user, highlight=False, score=None):
    return {
        "publish_id": publish.id,
        "notebook_id": publish.note_id,
        "user_id": publish.user_id,
        "is_mine": publish.user_id == user.id,
        "tag": publish.tag,
        "title": publish.note.title,
        "x": publish.particle_x if publish.particle_x is not None else 0,
        "y": publish.particle_y if publish.particle_y is not None else 0,
        "z": publish.particle_z if publish.particle_z is not None else 0,
        "color": publish.particle_color or particle_color(publish.tag_normalized),
        "size": publish.particle_size,
        "highlight": bool(highlight),
        "score": score,
        "published_at": publish.published_at,
    }


def particles(scope: str, user):
    return [serialize_particle(item, user, highlight=item.user_id == user.id) for item in publish_queryset(scope, user)[:1000]]


def search_particles(tag_value: str, scope: str, user):
    normalized = normalize_tag(tag_value)
    query_vector = embedding_text(normalized)
    qs = list(publish_queryset(scope, user)[:1000])
    limit = int(getattr(settings, "OCTOPUS_PLANET_SEARCH_LIMIT", 200) or 200)
    qdrant_scores = qdrant_search(query_vector, scope, user, limit)
    if qdrant_scores is not None:
        publish_map = {item.id: item for item in qs}
        return [
            serialize_particle(publish_map[publish_id], user, highlight=True, score=round(score, 4))
            for publish_id, score in sorted(qdrant_scores.items(), key=lambda item: item[1], reverse=True)
            if publish_id in publish_map
        ]
    scored = []
    for publish in qs:
        score = cosine_similarity(query_vector, publish.tag_vector or embedding_text(publish.tag_normalized))
        scored.append((score, publish))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        serialize_particle(publish, user, highlight=score >= 0.2, score=round(float(score), 4))
        for score, publish in scored[:limit]
    ]


def publish_detail(publish_id: int, user):
    publish = OctopusPlanetPublish.objects.select_related("note", "user").filter(id=publish_id, is_public=True).first()
    if not publish:
        raise OctopusPlanetError("发布记录不存在", 404)
    content = str(publish.note.content or "").strip()
    author_name = publish.user.get_full_name() or publish.user.username
    return {
        "publish_id": publish.id,
        "notebook_id": publish.note_id,
        "tag": publish.tag,
        "title": publish.note.title,
        "content_preview": content[:600],
        "is_mine": publish.user_id == user.id,
        "author": {
            "id": publish.user_id,
            "nickname": author_name,
        },
        "published_at": publish.published_at,
    }


def rebuild_particle_positions():
    publishes = list(OctopusPlanetPublish.objects.filter(is_public=True))
    for publish in publishes:
        vector = publish.tag_vector or embedding_text(publish.tag_normalized)
        x, y, z = project_vector(vector, publish.qdrant_point_id)
        publish.particle_x = x
        publish.particle_y = y
        publish.particle_z = z
        publish.particle_color = publish.particle_color or particle_color(publish.tag_normalized)
        publish.save(update_fields=["particle_x", "particle_y", "particle_z", "particle_color", "updated_at"])
    return len(publishes)
