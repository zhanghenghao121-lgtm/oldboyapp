from celery import shared_task

from .models import GenerationTask


@shared_task
def run_test_model_generation(task_id: int):
    task = GenerationTask.objects.select_related("character").filter(id=task_id).first()
    if not task:
        return
    task.status = GenerationTask.STATUS_RUNNING
    task.save(update_fields=["status", "updated_at"])
    character = task.character
    task.status = GenerationTask.STATUS_COMPLETED
    task.result_payload = {
        "message": "第一版未接真实3D生成API，已复用上传的测试GLB模型。",
        "model_url": character.model_url,
        "character_id": character.id,
    }
    task.save(update_fields=["status", "result_payload", "updated_at"])
