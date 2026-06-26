"""认证业务逻辑：注册时检查用户名唯一性，登录时验证密码并签发 JWT。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, Unauthorized
from app.core.security import create_token, hash_password, verify_password
from app.repositories.user_repo import UserRepo


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepo(db)

    async def register(self, username: str, password: str) -> dict:
        existing = await self.repo.get_by_username(username)
        if existing:
            raise BadRequest(code=40001, message="用户名已存在")
        hashed = hash_password(password)
        user = await self.repo.create(username, hashed)
        token = create_token({"user_id": user.id})
        return {"token": token, "user_id": user.id, "username": user.username}

    async def login(self, username: str, password: str) -> dict:
        user = await self.repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise Unauthorized("用户名或密码错误")
        token = create_token({"user_id": user.id})
        return {"token": token, "user_id": user.id, "username": user.username}
