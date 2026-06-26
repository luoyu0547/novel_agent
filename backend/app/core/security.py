"""认证与授权工具。

使用 bcrypt（通过 passlib）进行密码哈希，使用 HS256 JWT 生成 token。
``get_current_user`` 是认证守卫：解码 Bearer token 并查询用户。
"""
import datetime
import logging

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import Unauthorized
from app.models.user import User
from app.repositories.user_repo import UserRepo

logger = logging.getLogger("novel_agent")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict) -> str:
    """签发 JWT，将 data 中的字段（如 user_id）编码进 payload，自动添加过期时间。"""
    payload = data.copy()
    payload["exp"] = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise Unauthorized("token 已过期")
    except jwt.InvalidTokenError:
        raise Unauthorized("无效的 token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """认证守卫：解码 Bearer token，提取 user_id 并查询用户。用户不存在或 token 无效时抛出 Unauthorized。"""
    payload = decode_token(credentials.credentials)
    user_id = payload.get("user_id")
    if not user_id:
        raise Unauthorized("无效的 token")
    user = await UserRepo(db).get_by_id(user_id)
    if not user:
        raise Unauthorized("用户不存在")
    return user
