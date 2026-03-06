from django.conf import settings
from django.db import models
from decimal import Decimal


class AICustomerSetting(models.Model):
    enabled = models.BooleanField(default=True)
    tone_style = models.TextField(default="语气专业、耐心、简洁，像一位成熟产品经理。")
    base_prompt = models.TextField(
        default=(
            "你是网站AI客服。请优先依据知识库回答，必要时结合常识。"
            "如果知识库和常识都不足以支持可靠回答，请明确说无法确认，并输出 [NEED_HUMAN]。"
        )
    )
    resume_system_prompt = models.TextField(
        default=(
            "你是专业简历顾问。请基于职位名称、OCR识别的岗位要求和技能点分析结果，"
            "输出结构化、真实可填写的简历草稿。不得虚构具体经历，缺失信息必须标注[待填写]。"
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
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = (
        (STATUS_PENDING, "排队中"),
        (STATUS_RUNNING, "处理中"),
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
        (STATUS_CANCELED, "取消上传"),
    )

    title = models.CharField(max_length=200)
    source_name = models.CharField(max_length=255)
    source_key = models.CharField(max_length=255, blank=True, default="")
    source_url = models.URLField(max_length=1000, blank=True, default="")
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


class KnowledgeUploadSession(models.Model):
    STATUS_UPLOADING = "uploading"
    STATUS_COMPLETED = "completed"
    STATUS_ABORTED = "aborted"
    STATUS_CHOICES = (
        (STATUS_UPLOADING, "上传中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_ABORTED, "已取消"),
    )

    upload_id = models.CharField(max_length=64, unique=True)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    file_fingerprint = models.CharField(max_length=255, blank=True, default="")
    title = models.CharField(max_length=200, blank=True, default="")
    chunk_size = models.PositiveIntegerField(default=2 * 1024 * 1024)
    total_chunks = models.PositiveIntegerField(default=1)
    uploaded_chunks = models.JSONField(default=list, blank=True)
    completed_doc_id = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_UPLOADING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]


class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    title = models.CharField(max_length=120, default="新的对话")
    scene_type = models.CharField(max_length=32, default="general")
    summary = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


class UserProfileMemory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_memories")
    mem_key = models.CharField(max_length=64)
    mem_value = models.TextField()
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.70"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        unique_together = ("user", "mem_key")


class MemoryChunk(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memory_chunks")
    session = models.ForeignKey(ChatSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="memory_chunks")
    content = models.TextField()
    vector_id = models.CharField(max_length=64, unique=True)
    source = models.CharField(max_length=32, default="chat")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = (
        (ROLE_USER, "用户"),
        (ROLE_ASSISTANT, "AI"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session = models.ForeignKey(ChatSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages")
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
    skill_points = models.JSONField(default=list, blank=True)
    resume_text = models.TextField(blank=True, default="")
    pdf_url = models.URLField(max_length=1000, blank=True, default="")
    error_message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]


class AiHotItem(models.Model):
    source = models.CharField(max_length=32, default="aa1_douyin_hot")
    word = models.CharField(max_length=100, unique=True)
    position = models.IntegerField(null=True, blank=True)
    hot_value = models.CharField(max_length=64, blank=True, default="")
    raw_json = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "-id"]


class AiBloggerPost(models.Model):
    INPUT_MANUAL = "manual"
    INPUT_AUTO = "auto"
    INPUT_CHOICES = (
        (INPUT_MANUAL, "手动"),
        (INPUT_AUTO, "自动"),
    )

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "排队中"),
        (STATUS_RUNNING, "处理中"),
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
    )

    STAGE_TITLE = "title"
    STAGE_COPY = "copy"
    STAGE_IMAGES = "images"
    STAGE_DONE = "done"
    STAGE_CHOICES = (
        (STAGE_TITLE, "标题"),
        (STAGE_COPY, "文案"),
        (STAGE_IMAGES, "配图"),
        (STAGE_DONE, "完成"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_blogger_posts")
    input_mode = models.CharField(max_length=16, choices=INPUT_CHOICES, default=INPUT_MANUAL)
    hot_word = models.CharField(max_length=100)
    style_prompt = models.TextField(blank=True, default="")
    ratio = models.CharField(max_length=16, default="9:16")
    image_count = models.PositiveSmallIntegerField(default=1)
    status_text = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    stage_text = models.CharField(max_length=16, choices=STAGE_CHOICES, default=STAGE_TITLE)
    title = models.TextField(blank=True, default="")
    copy = models.TextField(blank=True, default="")
    selected_cover_key = models.CharField(max_length=255, blank=True, default="")
    error_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]


class AiBloggerAsset(models.Model):
    TYPE_IMAGE = "image"
    TYPE_VIDEO = "video"
    TYPE_CHOICES = (
        (TYPE_IMAGE, "图片"),
        (TYPE_VIDEO, "视频"),
    )

    post = models.ForeignKey(AiBloggerPost, on_delete=models.CASCADE, related_name="assets")
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    cos_key = models.CharField(max_length=255)
    url = models.URLField(max_length=1000, blank=True, default="")
    meta_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class AiBloggerVideoTask(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "排队中"),
        (STATUS_RUNNING, "处理中"),
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
    )

    post = models.ForeignKey(AiBloggerPost, on_delete=models.CASCADE, related_name="video_tasks")
    status_video = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    seedance_task_id = models.CharField(max_length=120, blank=True, default="")
    duration = models.PositiveSmallIntegerField(default=5)
    ratio = models.CharField(max_length=16, default="adaptive")
    generate_audio = models.BooleanField(default=True)
    watermark = models.BooleanField(default=False)
    video_asset = models.ForeignKey(AiBloggerAsset, null=True, blank=True, on_delete=models.SET_NULL)
    error_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
