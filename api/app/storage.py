import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_PUBLIC_ENDPOINT,
    MINIO_SECRET_KEY,
)


s3_client = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def ensure_bucket_exists():
    existing_buckets = s3_client.list_buckets()
    bucket_names = [bucket["Name"] for bucket in existing_buckets["Buckets"]]

    if MINIO_BUCKET not in bucket_names:
        s3_client.create_bucket(Bucket=MINIO_BUCKET)


def upload_file_to_storage(file):
    file_id = str(uuid.uuid4())
    object_key = f"{file_id}-{file.filename}"

    s3_client.upload_fileobj(
        file.file,
        MINIO_BUCKET,
        object_key,
        ExtraArgs={
            "ContentType": file.content_type or "application/octet-stream"
        },
    )

    return {
        "file_id": file_id,
        "filename": file.filename,
        "object_key": object_key,
        "bucket": MINIO_BUCKET,
        "content_type": file.content_type,
    }


def list_files_from_storage():
    response = s3_client.list_objects_v2(Bucket=MINIO_BUCKET)

    files = []

    for obj in response.get("Contents", []):
        files.append(
            {
                "object_key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            }
        )

    return {"bucket": MINIO_BUCKET, "files": files}


def get_file_from_storage(object_key: str):
    try:
        return s3_client.get_object(
            Bucket=MINIO_BUCKET,
            Key=object_key,
        )
    except ClientError:
        return None


def delete_file_from_storage(object_key: str):
    try:
        s3_client.head_object(Bucket=MINIO_BUCKET, Key=object_key)

        s3_client.delete_object(
            Bucket=MINIO_BUCKET,
            Key=object_key,
        )

        return True

    except ClientError:
        return False


def generate_share_url(object_key: str, ttl_seconds: int):
    try:
        s3_client.head_object(Bucket=MINIO_BUCKET, Key=object_key)

        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": MINIO_BUCKET,
                "Key": object_key,
            },
            ExpiresIn=ttl_seconds,
        )

        return presigned_url.replace(MINIO_ENDPOINT, MINIO_PUBLIC_ENDPOINT)

    except ClientError:
        return None