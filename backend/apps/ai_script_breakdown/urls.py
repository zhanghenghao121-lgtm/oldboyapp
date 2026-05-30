from django.urls import path

from apps.ai_script_breakdown.views import (
    script_breakdown_project_detail,
    script_breakdown_project_run,
    script_breakdown_projects,
    script_breakdown_segment_regenerate,
    script_breakdown_segment_regenerate_position,
)

urlpatterns = [
    path("ai-script-breakdown/projects", script_breakdown_projects),
    path("ai-script-breakdown/projects/<int:project_id>", script_breakdown_project_detail),
    path("ai-script-breakdown/projects/<int:project_id>/run", script_breakdown_project_run),
    path("ai-script-breakdown/segments/<int:segment_id>/regenerate", script_breakdown_segment_regenerate),
    path("ai-script-breakdown/segments/<int:segment_id>/regenerate-position", script_breakdown_segment_regenerate_position),
]
