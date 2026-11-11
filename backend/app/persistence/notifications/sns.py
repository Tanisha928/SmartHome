"""SNS client construction kept inside the persistence boundary."""

from typing import Any

import boto3
from botocore.client import BaseClient


def create_sns_client(client_kwargs: dict[str, Any]) -> BaseClient:
    return boto3.client("sns", **client_kwargs)
