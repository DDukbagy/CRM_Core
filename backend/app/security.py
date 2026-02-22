import os
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 토큰 유효기간 (24시간)

# 비밀번호 암호화 도구
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """비밀번호가 맞는지 확인"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """비밀번호를 암호화"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 토큰(신분증)을 발급"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt