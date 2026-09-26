from datetime import datetime, timedelta, UTC
import uuid
from typing import Optional, Dict
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# 密码哈希器
password_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def hash_password(plain: str) -> str:
    return password_context.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return password_context.verify(plain, hashed)

def create_access_token(subject: str, scope: str = "access") -> str:
    """签发门禁卡：信息装进 payload，用印章签名"""
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        'exp': expire,
        "sub": str(subject), # 持卡人身份
        "scope": scope,
        "jti": str(uuid.uuid4()) # 每张卡唯一编号，防重放
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Optional[Dict]:
    """验卡：解码 + 验签 + 查过期，一步到位"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

def verify_token(token: str, scope: str = None) -> Optional[Dict]:
    """验卡 + 查卡上通行区域：scope 不匹配返回 None"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if scope and payload.get("scope") != scope:
            return None
        return payload
    except JWTError:
        return None