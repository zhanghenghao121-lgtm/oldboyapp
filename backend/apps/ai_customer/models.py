from django.conf import settings
from django.db import models


class AICustomerSetting(models.Model):
    enabled = models.BooleanField(default=True)
    tone_style = models.TextField(default="语气专业、耐心、简洁，像一位成熟产品经理。")
    base_prompt = models.TextField(
        default=(
            "你是网站AI客服。请优先依据知识库回答，必要时结合常识。"
            "如果知识库和常识都不足以支持可靠回答，请明确说无法确认，并输出 [NEED_HUMAN]。"
        )
    )
    no_answer_text = models.CharField(max_length=255, default="这个问题需要人工客服进一步处理，我已经帮你转接。")
    feishu_bot_config_url = models.URLField(max_length=500, blank=True, default="")
    feishu_webhook_url = models.URLField(max_length=500, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def singleton(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class KnowledgeDocument(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "处理中"),
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
    )

    title = models.CharField(max_length=200)
    source_name = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    chunk_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class KnowledgeChunk(models.Model):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.PositiveIntegerField(default=0)
    text = models.TextField()
    vector_id = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = (
        (ROLE_USER, "用户"),
        (ROLE_ASSISTANT, "AI"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class HumanHandoverTicket(models.Model):
    STATUS_UNREAD = "unread"
    STATUS_READ = "read"
    STATUS_IGNORED = "ignored"
    STATUS_CHOICES = (
        (STATUS_UNREAD, "未读"),
        (STATUS_READ, "已读"),
        (STATUS_IGNORED, "忽略"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.TextField()
    ai_reply = models.TextField(blank=True, default="")
    admin_reply = models.TextField(blank=True, default="")
    synced_to_knowledge = models.BooleanField(default=False)
    attachments = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_UNREAD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]


class HumanReplyClearState(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_reply_clear_state")
    cleared_at = models.DateTimeField()

    class Meta:
        ordering = ["-cleared_at"]


class ResumeAssistantTask(models.Model):
    STATUS_CREATED = "created"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_CREATED, "已创建"),
        (STATUS_RUNNING, "处理中"),
        (STATUS_SUCCEEDED, "成功"),
        (STATUS_FAILED, "失败"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resume_tasks")
    request_id = models.CharField(max_length=64, unique=True)
    job_title = models.CharField(max_length=120)
    image_urls = models.JSONField(default=list, blank=True)
    rois = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
    progress = models.PositiveSmallIntegerField(default=0)
    cost_points = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunded = models.BooleanField(default=False)
    ocr_text = models.TextField(blank=True, default="")
    resume_text = models.TextField(blank=True, default="")
    pdf_url = models.URLField(max_length=1000, blank=True, default="")
    error_message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
