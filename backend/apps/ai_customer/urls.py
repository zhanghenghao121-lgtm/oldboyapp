from django.urls import path

from apps.ai_customer.views import (
    chat_history,
    chat_stream,
    human_replies,
    clear_human_replies,
    resume_assistant_generate,
    resume_assistant_task_create,
    resume_assistant_task_detail,
)
from apps.ai_customer.blogger_views import (
    ai_blogger_hotwords,
    ai_blogger_hotwords_refresh,
    ai_blogger_post_create,
    ai_blogger_post_detail,
    ai_blogger_select_cover,
    ai_blogger_video_create,
    ai_blogger_video_detail,
)
from apps.ai_customer.admin_views import (
    ai_cs_docs,
    ai_cs_doc_delete,
    ai_cs_settings,
    ai_cs_upload_knowledge_chunk,
    ai_cs_upload_knowledge_complete,
    ai_cs_upload_knowledge_init,
    ai_cs_upload_knowledge_status,
    ai_cs_ticket_sync_knowledge,
    ai_cs_tickets,
    ai_cs_ticket_update,
    ai_cs_upload_knowledge,
)

urlpatterns = [
    path("ai-customer/history", chat_history),
    path("ai-customer/human-replies", human_replies),
    path("ai-customer/human-replies/clear", clear_human_replies),
    path("ai-customer/resume-assistant/generate", resume_assistant_generate),
    path("ai-customer/resume-assistant/tasks", resume_assistant_task_create),
    path("ai-customer/resume-assistant/tasks/<int:task_id>", resume_assistant_task_detail),
    path("ai-customer/chat/stream", chat_stream),
    path("ai-blogger/hotwords", ai_blogger_hotwords),
    path("ai-blogger/hotwords/refresh", ai_blogger_hotwords_refresh),
    path("ai-blogger/posts", ai_blogger_post_create),
    path("ai-blogger/posts/<int:post_id>", ai_blogger_post_detail),
    path("ai-blogger/posts/<int:post_id>/select-cover", ai_blogger_select_cover),
    path("ai-blogger/posts/<int:post_id>/video", ai_blogger_video_create),
    path("ai-blogger/posts/<int:post_id>/video/status", ai_blogger_video_detail),

    path("console/ai-cs/settings", ai_cs_settings),
    path("console/ai-cs/knowledge/docs", ai_cs_docs),
    path("console/ai-cs/knowledge/upload", ai_cs_upload_knowledge),
    path("console/ai-cs/knowledge/upload/init", ai_cs_upload_knowledge_init),
    path("console/ai-cs/knowledge/upload/chunk", ai_cs_upload_knowledge_chunk),
    path("console/ai-cs/knowledge/upload/status", ai_cs_upload_knowledge_status),
    path("console/ai-cs/knowledge/upload/complete", ai_cs_upload_knowledge_complete),
    path("console/ai-cs/knowledge/docs/<int:doc_id>", ai_cs_doc_delete),
    path("console/ai-cs/tickets", ai_cs_tickets),
    path("console/ai-cs/tickets/sync-knowledge", ai_cs_ticket_sync_knowledge),
    path("console/ai-cs/tickets/<int:ticket_id>", ai_cs_ticket_update),
]
