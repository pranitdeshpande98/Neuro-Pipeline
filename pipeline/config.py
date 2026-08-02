from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    s3_region: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            s3_endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
            s3_access_key=_required("S3_ACCESS_KEY"),
            s3_secret_key=_required("S3_SECRET_KEY"),
            s3_bucket=os.environ.get("S3_BUCKET", "neuro"),
            s3_region=os.environ.get("S3_REGION", "us-east-1"),
        )