from django.contrib import admin

from .models import Artifact, PipelineRun, SubjectJob


class SubjectJobInline(admin.TabularInline):
    model = SubjectJob
    extra = 0
    fields = ("subject", "k8s_job_name", "status", "attempts", "finished_at")
    readonly_fields = ("k8s_job_name", "attempts", "finished_at")
    show_change_link = True


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "dataset", "pipeline_version", "status",
        "created_at", "finished_at",
    )
    list_filter = ("status", "dataset")
    readonly_fields = ("created_at", "started_at", "finished_at")
    inlines = [SubjectJobInline]


@admin.register(SubjectJob)
class SubjectJobAdmin(admin.ModelAdmin):
    list_display = (
        "k8s_job_name", "run", "subject", "status",
        "attempts", "exit_code", "last_synced_at",
    )
    list_filter = ("status", "run__dataset")
    search_fields = ("k8s_job_name", "subject__external_id")
    list_select_related = ("run", "subject")


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ("kind", "job", "storage_key", "size_bytes", "created_at")
    list_filter = ("kind",)
    search_fields = ("storage_key",)