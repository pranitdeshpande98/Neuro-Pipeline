from django.db import models


class Modality(models.TextChoices):
    EEG = "EEG", "EEG"
    FMRI = "FMRI", "fMRI"


class Dataset(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    modality = models.CharField(max_length=8, choices=Modality.choices)
    source_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.slug


class Subject(models.Model):
    dataset = models.ForeignKey(
        Dataset, on_delete=models.PROTECT, related_name="subjects"
    )
    external_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["dataset", "external_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "external_id"],
                name="uniq_subject_per_dataset",
            )
        ]

    def __str__(self):
        return f"{self.dataset.slug}/{self.external_id}"


class Recording(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="recordings"
    )
    external_id = models.CharField(max_length=64)
    task = models.CharField(max_length=64, blank=True)
    run_index = models.PositiveSmallIntegerField(null=True, blank=True)

    # Populated at ingestion, once the file is actually read
    n_channels = models.PositiveSmallIntegerField(null=True, blank=True)
    sfreq_hz = models.FloatField(null=True, blank=True)
    duration_s = models.FloatField(null=True, blank=True)

    # Object storage
    storage_key = models.CharField(max_length=512, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    ingested_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["subject", "run_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "external_id"],
                name="uniq_recording_per_subject",
            )
        ]
        indexes = [models.Index(fields=["task"])]

    def __str__(self):
        return self.external_id