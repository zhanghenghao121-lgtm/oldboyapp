from django.urls import path

from apps.ai_customer.views import chat_history, chat_stream
from apps.ai_customer.admin_views import (
    ai_cs_docs,
    ai_cs_settings,
    ai_cs_tickets,
    ai_cs_ticket_update,
    ai_cs_upload_knowledge,
)

urlpatterns = [
    path("ai-customer/history", chat_history),
    path("ai-customer/chat/stream", chat_stream),

    path("console/ai-cs/settings", ai_cs_settings),
    path("console/ai-cs/knowledge/docs", ai_cs_docs),
    path("console/ai-cs/knowledge/upload", ai_cs_upload_knowledge),
    path("console/ai-cs/tickets", ai_cs_tickets),
    path("console/ai-cs/tickets/<int:ticket_id>", ai_cs_ticket_update),
]
