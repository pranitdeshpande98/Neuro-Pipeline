from django.conf import settings
from django.db import models

from apps.catalog.models import Dataset, Subject


class RunStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SUBMITTED = "SUBMITTED", "Submitted"
    RUNNING = "RUNNING", "Running"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


TERMINAL_STATUSES = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
)


class PipelineRun(models.Model):
    """A batch: one user-initiated execution over many subjects."""

    dataset = models.ForeignKey(
        Dataset, on_delete=models.PROTECT, related_name="runs"
    )
    pipeline_version = models.CharField(max_length=64)
    parameters = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=16,
        choices=RunStatus.choices,
        default=RunStatus.PENDING,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pipeline_runs",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"run-{self.pk} [{self.status}]"


class SubjectJob(models.Model):
    """One Kubernetes Job: one subject, one run."""

    run = models.ForeignKey(
        PipelineRun, on_delete=models.CASCADE, related_name="jobs"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="jobs"
    )

    k8s_job_name = models.CharField(
        max_length=63, unique=True, null=True, blank=True
    )

    status = models.CharField(
        max_length=16, choices=RunStatus.choices, default=RunStatus.PENDING
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    exit_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    metrics = models.JSONField(default=dict, blank=True)
    result_key = models.CharField(max_length=512, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["run", "subject"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "subject"], name="uniq_subject_per_run"
            )
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["run", "status"]),
        ]

    def __str__(self):
        return f"{self.k8s_job_name or 'unsubmitted'} [{self.status}]"


class Artifact(models.Model):
    """A file produced by a job, stored in object storage."""

    class Kind(models.TextChoices):
        EPOCHS = "EPOCHS", "Epoched data"
        PSD = "PSD", "Power spectral density"
        CONNECTIVITY = "CONNECTIVITY", "Connectivity matrix"
        QC = "QC", "QC report"
        FIGURE = "FIGURE", "Figure"

    job = models.ForeignKey(
        SubjectJob, on_delete=models.CASCADE, related_name="artifacts"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    storage_key = models.CharField(max_length=512)
    content_type = models.CharField(max_length=128, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["job", "kind"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "kind", "storage_key"],
                name="uniq_artifact_per_job",
            )
        ]

    def __str__(self):
        return f"{self.kind}:{self.storage_key}"