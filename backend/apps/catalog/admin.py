from django.contrib import admin

from .models import Dataset, Recording, Subject


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "modality", "created_at")
    search_fields = ("slug", "name")


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("external_id", "dataset", "created_at")
    list_filter = ("dataset", "dataset__modality")
    search_fields = ("external_id",)
    list_select_related = ("dataset",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = (
        "external_id", "subject", "task", "run_index",
        "sfreq_hz", "duration_s", "ingested_at",
    )
    list_filter = ("task", "subject__dataset")
    search_fields = ("external_id", "subject__external_id")
    list_select_related = ("subject",)