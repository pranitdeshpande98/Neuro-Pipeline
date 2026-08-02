from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Dataset, Modality, Recording, Subject
from apps.common.edf import read_edf_header
from apps.common.storage import (
    ensure_bucket,
    object_exists,
    sha256_file,
    upload_file,
)

BASE_URL = "https://physionet.org/files/eegmmidb/1.0.0"
DATASET_SLUG = "eegmmidb"

# Known annotation errors; excluded by convention in the literature.
EXCLUDED_SUBJECTS = {38, 88, 89, 92, 100, 104}

RUN_TASKS = {
    1: "baseline_eyes_open",
    2: "baseline_eyes_closed",
    3: "fist_lr_executed",
    4: "fist_lr_imagined",
    5: "hands_feet_executed",
    6: "hands_feet_imagined",
    7: "fist_lr_executed",
    8: "fist_lr_imagined",
    9: "hands_feet_executed",
    10: "hands_feet_imagined",
    11: "fist_lr_executed",
    12: "fist_lr_imagined",
    13: "hands_feet_executed",
    14: "hands_feet_imagined",
}


def select_subjects(count: int) -> list[int]:
    chosen: list[int] = []
    n = 1
    while len(chosen) < count and n <= 109:
        if n not in EXCLUDED_SUBJECTS:
            chosen.append(n)
        n += 1
    return chosen


class Command(BaseCommand):
    help = "Download EEGMMIDB recordings, upload to object storage, register metadata."

    def add_arguments(self, parser):
        parser.add_argument("--subjects", type=int, default=20)
        parser.add_argument("--runs", type=int, nargs="+", default=[4, 8, 12])
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--delay", type=float, default=0.5)
        parser.add_argument(
            "--cache-dir",
            type=Path,
            default=Path(settings.BASE_DIR).parent / "data" / "eegmmidb",
        )

    def handle(self, *args, **opts):
        ensure_bucket()

        dataset, _ = Dataset.objects.get_or_create(
            slug=DATASET_SLUG,
            defaults={
                "name": "EEG Motor Movement/Imagery Database",
                "modality": Modality.EEG,
                "source_url": f"{BASE_URL}/",
            },
        )

        cache_dir = opts["cache_dir"].resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)

        subjects = select_subjects(opts["subjects"])
        self.stdout.write(
            f"Ingesting {len(subjects)} subjects x {len(opts['runs'])} runs "
            f"into cache {cache_dir}"
        )

        for n in subjects:
            sid = f"S{n:03d}"
            subject, _ = Subject.objects.get_or_create(
                dataset=dataset, external_id=sid
            )
            self.stdout.write(sid)
            for run_index in opts["runs"]:
                self._ingest_one(subject, sid, run_index, cache_dir, opts)

    def _ingest_one(self, subject, sid, run_index, cache_dir, opts):
        rid = f"{sid}R{run_index:02d}"
        local = cache_dir / sid / f"{rid}.edf"
        key = f"raw/{DATASET_SLUG}/{sid}/{rid}.edf"
        url = f"{BASE_URL}/{sid}/{rid}.edf"

        recording, _ = Recording.objects.get_or_create(
            subject=subject,
            external_id=rid,
            defaults={"task": RUN_TASKS.get(run_index, ""), "run_index": run_index},
        )

        if recording.ingested_at and not opts["force"] and object_exists(key):
            self.stdout.write(f"  skip     {rid}")
            return

        if not local.exists():
            local.parent.mkdir(parents=True, exist_ok=True)
            self.stdout.write(f"  download {rid}")
            self._download(url, local)
            time.sleep(opts["delay"])

        header = read_edf_header(local)
        checksum = sha256_file(local)

        if opts["force"] or not object_exists(key):
            upload_file(local, key)

        recording.task = RUN_TASKS.get(run_index, "")
        recording.run_index = run_index
        recording.n_channels = header.n_channels
        recording.sfreq_hz = header.sfreq_hz
        recording.duration_s = header.duration_s
        recording.storage_key = key
        recording.checksum_sha256 = checksum
        recording.size_bytes = local.stat().st_size
        recording.ingested_at = timezone.now()
        recording.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"  ok       {rid}  {header.n_channels}ch "
                f"@ {header.sfreq_hz:.0f}Hz  {header.duration_s:.0f}s"
            )
        )

    @staticmethod
    def _download(url: str, dest: Path) -> None:
        tmp = dest.with_suffix(dest.suffix + ".part")
        request = urllib.request.Request(
            url, headers={"User-Agent": "neuro-pipeline/0.1 (portfolio project)"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            with open(tmp, "wb") as fh:
                while chunk := response.read(1 << 20):
                    fh.write(chunk)
        tmp.replace(dest)