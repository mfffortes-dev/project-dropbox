from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.storage import (
    delete_file_from_storage,
    generate_share_url,
    get_file_from_storage,
    list_files_from_storage,
    upload_file_to_storage,
)


router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    return upload_file_to_storage(file)


@router.get("")
def list_files():
    return list_files_from_storage()


@router.get("/{object_key}")
def download_file(object_key: str):
    response = get_file_from_storage(object_key)

    if response is None:
        raise HTTPException(status_code=404, detail="File not found")

    file_stream = response["Body"]
    content_type = response.get("ContentType", "application/octet-stream")

    return StreamingResponse(
        file_stream,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{object_key}"'
        },
    )


@router.delete("/{object_key}")
def delete_file(object_key: str):
    deleted = delete_file_from_storage(object_key)

    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "message": "File deleted successfully",
        "object_key": object_key,
    }


@router.post("/{object_key}/share")
def share_file(object_key: str, ttl_seconds: int = 3600):
    url = generate_share_url(object_key, ttl_seconds)

    if url is None:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "object_key": object_key,
        "ttl_seconds": ttl_seconds,
        "url": url,
    }