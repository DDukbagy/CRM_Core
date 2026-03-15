import logging
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")


def _get_s3_client():
    if not ACCESS_KEY or not SECRET_KEY or not BUCKET_NAME:
        logger.error("AWS credentials or bucket name missing")
        return None
    return boto3.client(
        "s3",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
        endpoint_url=f"https://s3.{REGION}.amazonaws.com",
        config=Config(signature_version="s3v4", region_name=REGION),
    )


def upload_file_to_s3(file_obj, filename: str, content_type: str, folder: str = "uploads") -> dict | None:
    """직접 업로드 (서버 경유). content_type을 반드시 지정."""
    s3 = _get_s3_client()
    if not s3:
        return None
    s3_key = f"{folder}/{filename}"
    try:
        s3.upload_fileobj(file_obj, BUCKET_NAME, s3_key, ExtraArgs={"ContentType": content_type})
        return {"url": f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{s3_key}", "key": s3_key}
    except Exception as e:
        logger.error("S3 upload error: %s", e)
        return None


def create_presigned_url(s3_key: str, expiration: int = 3600) -> str | None:
    """조회용 임시 접근 URL 생성"""
    s3 = _get_s3_client()
    if not s3:
        return None
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.error("S3 presign error: %s", e)
        return None


def create_presigned_upload_url(s3_key: str, content_type: str, expiration: int = 300) -> str | None:
    """앱 직접 업로드용 presigned PUT URL (기본 5분 유효)"""
    s3 = _get_s3_client()
    if not s3:
        return None
    try:
        return s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key, "ContentType": content_type},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.error("S3 presign upload error: %s", e)
        return None


MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100 MB


def create_presigned_post(
    s3_key: str,
    content_type: str,
    max_bytes: int,
    expiration: int = 300,
) -> dict | None:
    """클라이언트 직접 업로드용 presigned POST.
    content-length-range 조건으로 파일 크기를 S3 레벨에서 제한한다.
    반환: {"url": "https://...", "fields": {...}} — 없으면 None.
    """
    s3 = _get_s3_client()
    if not s3:
        return None
    try:
        return s3.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=expiration,
        )
    except ClientError as e:
        logger.error("S3 presigned POST error: %s", e)
        return None


def delete_file_from_s3(s3_key: str) -> bool:
    s3 = _get_s3_client()
    if not s3:
        return False
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        logger.info("Deleted S3 object: %s", s3_key)
        return True
    except ClientError as e:
        logger.error("S3 delete error: %s", e)
        return False
