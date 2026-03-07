from django.contrib import admin

from apps.ai_memory.models import (
    AIConversationSummary,
    AIMessage,
    AIMemoryWriteLog,
    AISession,
    AIUserFact,
)


@admin.register(AISession)
class AISessionAdmin(admin.ModelAdmin):
    list_display = ("id", "session_uuid", "user", "scene", "status", "last_active_at")
    list_filter = ("status", "scene")
    search_fields = ("session_uuid", "user__username", "title")


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "user", "role", "token_estimate", "created_at")
    list_filter = ("role", "message_type")
    search_fields = ("content", "user__username")


@admin.register(AIConversationSummary)
class AIConversationSummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "user", "summary_type", "task_stage", "version", "is_active", "updated_at")
    list_filter = ("summary_type", "is_active", "task_stage")


@admin.register(AIUserFact)
class AIUserFactAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "fact_key", "fact_type", "confidence", "status", "version", "updated_at")
    list_filter = ("fact_type", "status")
    search_fields = ("fact_key", "fact_value", "user__username")


@admin.register(AIMemoryWriteLog)
class AIMemoryWriteLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session", "decision", "target_layer", "created_at")
    list_filter = ("decision", "target_layer")
    search_fields = ("reason",)

