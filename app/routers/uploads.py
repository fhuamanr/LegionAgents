"""Upload APIs."""

from email.parser import BytesParser
from email.policy import default

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies.container import get_execution_service
from app.schemas import UploadResponse, UserStoryUploadRequest
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/user-stories", response_model=UploadResponse, status_code=201)
async def upload_user_story(
    request: UserStoryUploadRequest,
    service: ExecutionService = Depends(get_execution_service),
) -> UploadResponse:
    return await service.upload_user_story(request)


@router.post("/files", response_model=tuple[UploadResponse, ...], status_code=201)
async def upload_story_files(
    request: Request,
    service: ExecutionService = Depends(get_execution_service),
) -> tuple[UploadResponse, ...]:
    extracted = await _extract_uploads(request)
    uploads: list[UploadResponse] = []
    for file_name, content, content_type in extracted:
        uploads.append(
            await service.upload_file(
                file_name=file_name,
                content=content,
                content_type=content_type,
            )
        )
    return tuple(uploads)


async def _extract_uploads(request: Request) -> tuple[tuple[str, bytes, str | None], ...]:
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if content_type.startswith("multipart/form-data"):
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8") + body
        )
        files: list[tuple[str, bytes, str | None]] = []
        for part in message.iter_parts():
            disposition = part.get("content-disposition", "")
            if "form-data" not in disposition or "filename=" not in disposition:
                continue
            files.append(
                (
                    part.get_filename() or "upload.txt",
                    part.get_payload(decode=True) or b"",
                    part.get_content_type(),
                )
            )
        if not files:
            raise HTTPException(status_code=400, detail="multipart request did not include a file part")
        return tuple(files)
    file_name = request.headers.get("x-file-name", "upload.txt")
    return ((file_name, body, content_type or None),)
