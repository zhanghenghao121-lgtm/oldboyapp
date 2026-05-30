from django.contrib import admin

from apps.ai_script_breakdown.models import (
    AiScriptAsset,
    AiScriptBreakdownProject,
    AiScriptSceneBlock,
    AiScriptShotLine,
    AiScriptShotSegment,
)


admin.site.register(AiScriptBreakdownProject)
admin.site.register(AiScriptAsset)
admin.site.register(AiScriptSceneBlock)
admin.site.register(AiScriptShotSegment)
admin.site.register(AiScriptShotLine)
