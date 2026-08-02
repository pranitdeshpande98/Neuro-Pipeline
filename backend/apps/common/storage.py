import hashlib
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings


@lru_cache(maxsize=1)
def get_s3_client():
    """A single shared boto3 client. Clients are thread-safe and expensive
    to build, so we cache rather than constructing one per call."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def ensure_bucket(name: str | None = None) -> str:
    name = name or settings.S3_BUCKET
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=name)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code not in ("404", "NoSuchBucket"):
            raise
        client.create_bucket(Bucket=name)
    return name


def object_exists(key: str, bucket: str | None = None) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=bucket or settings.S3_BUCKET, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
    return True


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash in chunks so memory use stays flat regardless of file size."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload_file(path: Path, key: str, bucket: str | None = None) -> None:
    get_s3_client().upload_file(str(path), bucket or settings.S3_BUCKET, key)


def download_file(key: str, path: Path, bucket: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    get_s3_client().download_file(bucket or settings.S3_BUCKET, key, str(path))