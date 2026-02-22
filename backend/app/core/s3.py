import boto3
import os
from botocore.exceptions import NoCredentialsError, ClientError
from botocore.config import Config
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

def _get_s3_client():
    """S3 클라이언트 생성 헬퍼"""
    if not ACCESS_KEY or not SECRET_KEY or not BUCKET_NAME:
        print("Error: AWS Credentials or Bucket Name missing.")
        return None
    
    # 서명 버전 4 - 서울 리전 필수
    s3_config = Config(
        signature_version='s3v4',
        region_name=REGION
    )

    return boto3.client(
        's3',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
        endpoint_url=f"https://s3.{REGION}.amazonaws.com",
        config=s3_config
    )

def upload_file_to_s3(file_obj, filename: str, folder: str = "uploads") -> dict | None:
    """파일 업로드"""
    s3 = _get_s3_client()
    if not s3: return None

    s3_key = f"{folder}/{filename}"

    try:
        s3.upload_fileobj(
            file_obj,
            BUCKET_NAME,
            s3_key,
            ExtraArgs={'ContentType': 'image/jpeg'} 
        )
        # 반환하는 URL도 서울 리전 명시
        url = f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{s3_key}"
        return {"url": url, "key": s3_key}

    except Exception as e:
        print(f"S3 Upload Error: {e}")
        return None

def create_presigned_url(s3_key: str, expiration=3600) -> str | None:
    """[조회용] 임시 접근 URL 생성"""
    s3 = _get_s3_client()
    if not s3: return None

    try:
        response = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        print(f"S3 Presign Error: {e}")
        return None

def delete_file_from_s3(s3_key: str) -> bool:
    """[삭제용] 파일 영구 삭제"""
    s3 = _get_s3_client()
    if not s3: return False

    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        print(f"🗑️ Deleted S3 object: {s3_key}")
        return True
    except ClientError as e:
        print(f"S3 Delete Error: {e}")
        return False