from django.conf import settings
from django.db import models
from django.db.models import Q


class AISession(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "活跃"),
        (STATUS_ARCHIVED, "归档"),
    )

    session_uuid = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_mem_sessions")
    title = models.CharField(max_length=255, blank=True, default="")
    scene = models.CharField(max_length=64, default="general")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_sessions"
        indexes = [
            models.Index(fields=["user", "last_active_at"]),
            models.Index(fields=["status"]),
        ]


class AIMessage(models.Model):
    session = models.ForeignKey(AISession, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_mem_messages")
    role = models.CharField(max_length=16)
    content = models.TextField()
    token_estimate = models.IntegerField(default=0)
    message_type = models.CharField(max_length=32, default="chat")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_messages"
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]


class AIConversationSummary(models.Model):
    TYPE_RECENT = "recent_context"
    TYPE_CHOICES = ((TYPE_RECENT, "近期脉络"),)

    session = models.ForeignKey(AISession, on_delete=models.CASCADE, related_name="summaries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_mem_summaries")
    summary_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_RECENT)
    task_stage = models.CharField(max_length=64, blank=True, default="")
    current_goal = models.CharField(max_length=500, blank=True, default="")
    recent_decisions = models.JSONField(default=list, blank=True)
    open_questions = models.JSONField(default=list, blank=True)
    important_entities = models.JSONField(default=list, blank=True)
    next_action = models.CharField(max_length=500, blank=True, default="")
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_conversation_summaries"
        indexes = [
            models.Index(fields=["session", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]


class AIUserFact(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "生效"),
        (STATUS_INACTIVE, "失效"),
        (STATUS_DELETED, "删除"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_mem_facts")
    fact_key = models.CharField(max_length=128)
    fact_value = models.TextField()
    fact_type = models.CharField(max_length=64, default="general")
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0.800)
    source = models.CharField(max_length=32, default="model_extract")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ai_user_facts"
        indexes = [
            models.Index(fields=["user", "fact_type"]),
            models.Index(fields=["user", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "fact_key"],
                condition=Q(status="active"),
                name="uniq_ai_user_fact_active",
            )
        ]


class AIMemoryWriteLog(models.Model):
    DECISION_WRITE_FACT = "write_fact"
    DECISION_WRITE_SUMMARY = "write_summary"
    DECISION_WRITE_VECTOR = "write_vector"
    DECISION_WINDOW_ONLY = "window_only"
    DECISION_DISCARD = "discard"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_mem_write_logs")
    session = models.ForeignKey(AISession, null=True, blank=True, on_delete=models.SET_NULL, related_name="write_logs")
    source_message_id = models.BigIntegerField(default=0)
    decision = models.CharField(max_length=32)
    target_layer = models.CharField(max_length=32)
    reason = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_memory_write_logs"
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["session", "created_at"]),
        ]
