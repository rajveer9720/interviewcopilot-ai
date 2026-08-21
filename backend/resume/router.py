"""Resume domain — FastAPI router using Google Cloud Storage."""

import uuid
import io
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from google.cloud import storage

from backend.core.database import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.models import User
from backend.resume.models import Resume
from backend.resume.parser import ResumeParser
from backend.config import settings

router = APIRouter()
parser = ResumeParser()

ALLOWED_TYPES = {"application/pdf", "application/msword",
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/", status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Only PDF and Word documents are supported.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File size exceeds 5MB limit.")

    # Parse resume
    parsed = parser.parse(content, file.filename)

    # Upload to GCS
    storage_key = f"resumes/{current_user.id}/{uuid.uuid4()}/{file.filename}"
    _upload_to_gcs(content, storage_key, file.content_type)

    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        storage_key=storage_key,
        parsed_data=parsed,
        is_active=True,
    )
    db.add(resume)
    await db.flush()

    return {
        "id": str(resume.id),
        "filename": resume.filename,
        "skills": parsed.get("skills", []),
        "created_at": resume.created_at.isoformat(),
    }


@router.get("/")
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )
    resumes = result.scalars().all()
    return [
        {"id": str(r.id), "filename": r.filename, "is_active": r.is_active,
         "skills": (r.parsed_data or {}).get("skills", []),
         "created_at": r.created_at.isoformat()}
        for r in resumes
    ]


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(404, "Resume not found.")
    await db.delete(resume)


def _upload_to_gcs(content: bytes, key: str, content_type: str):
    """Upload file to Google Cloud Storage."""
    try:
        # If a credentials file path is provided, use it; otherwise rely on ADC.
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            credentials_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
            if not credentials_path.is_absolute():
                credentials_path = Path(__file__).resolve().parent.parent / credentials_path
            client = storage.Client.from_service_account_json(str(credentials_path))
        else:
            client = storage.Client()

        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(key)
        blob.upload_from_string(content, content_type=content_type)
    except Exception as e:
        raise HTTPException(500, f"Storage upload failed: {e}")
