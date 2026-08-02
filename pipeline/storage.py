from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config

from pipeline.config import Settings


class ObjectStore:
    """Thin S3 wrapper.

    Deliberately duplicated from the Django side (apps/common/storage.py):
    the web and pipeline images share no dependencies, and neither package
    may import the other. ~50 lines of duplication is the price of that
    boundary; a shared installable package would be the alternative.
    """

    def __init__(self, settings: Settings):
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def download(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self._bucket, key, str(dest))
        return dest

    def upload(self, src: Path, key: str, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else None
        self._client.upload_file(str(src), self._bucket, key, ExtraArgs=extra)

    def read_json(self, key: str) -> Any:
        body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        return json.loads(body)

    def write_json(self, key: str, payload: Any) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=json.dumps(payload, indent=2).encode(),
            ContentType="application/json",
        )