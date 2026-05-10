import os
import uuid

import boto3
from botocore.client import Config
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse


app = FastAPI(title="Cloud File Storage API")


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "user-files")


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


@app.on_event("startup")
def startup_event():
    ensure_bucket_exists()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
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

@app.get("/files")
def list_files():
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


@app.get("/files/{object_key}")
def download_file(object_key: str):
    try:
        response = s3_client.get_object(
            Bucket=MINIO_BUCKET,
            Key=object_key,
        )

        file_stream = response["Body"]
        content_type = response.get("ContentType", "application/octet-stream")

        return StreamingResponse(
            file_stream,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{object_key}"'
            },
        )

    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="File not found")

    
@app.delete("/files/{object_key}")
def delete_file(object_key: str):
    try:
        s3_client.head_object(Bucket=MINIO_BUCKET, Key=object_key)

        s3_client.delete_object(
            Bucket=MINIO_BUCKET,
            Key=object_key,
        )

        return {
            "message": "File deleted successfully",
            "object_key": object_key,
        }

    except s3_client.exceptions.ClientError:
        raise HTTPException(status_code=404, detail="File not found")


@app.post("/files/{object_key}/share")
def share_file(object_key: str, ttl_seconds: int = 3600):
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

        return {
            "object_key": object_key,
            "ttl_seconds": ttl_seconds,
            "url": presigned_url,
        }

    except s3_client.exceptions.ClientError:
        raise HTTPException(status_code=404, detail="File not found")
    