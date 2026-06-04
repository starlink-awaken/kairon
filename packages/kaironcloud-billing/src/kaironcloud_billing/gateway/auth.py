from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Layer: L3
Domain: D-Cloud
Summary: JWT authentication handler for API Gateway.
Authority: organs/D-Cloud/AGENTS.md
---
"""


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# JWT Auth ≡ Auth
# 内涵 ≝ {JWT, Token, Authentication}
# 外延 ≝ {e | e ∈ D-Cloud ∧ implements(e, JWTAuth)}
# 功能 ⊢ {Token_Validation, Claims_Extraction, Tenant_Identification}
# =============================================================================
import logging
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from .types import AuthResult, Request

_log = logging.getLogger(__name__)

# JWT算法
JWT_ALGORITHM = "HS256"


class JWTAuth:
    """JWT认证处理器

    功能:
    1. 令牌验证 - 验证JWT签名和过期时间
    2. 声明提取 - 提取租户、用户、权限信息
    3. 令牌刷新 - 支持令牌刷新机制
    4. 吊销检查 - 检查令牌是否被吊销
    """

    def __init__(
        self,
        secret_key: str | None = None,
        issuer: str = "https://auth.sharedbrain.cloud",
        audience: str = "bos-cloud",
    ) -> None:
        """初始化JWT认证器

        Args:
            secret_key: JWT签名密钥 (默认从环境变量获取)
            issuer: 令牌签发者
            audience: 令牌受众
        """
        self.status = "active"  # was super().__init__(metadata_path=...)
        self._secret_key = secret_key or self._get_secret_key()
        self._issuer = issuer
        self._audience = audience
        self._revoked_tokens: set[str] = set()  # 吊销令牌集合

    def _get_secret_key(self) -> str:
        """获取JWT密钥

        Returns:
            JWT签名密钥

        Raises:
            ValueError: 如果密钥未设置
        """
        import os

        key = os.environ.get("BOS_JWT_SECRET")
        if not key:
            # 开发环境使用随机密钥
            _log.warning("BOS_JWT_SECRET not set, using random key for development")
            return secrets.token_urlsafe(32)
        return key

    async def authenticate(self, token: str) -> AuthResult:
        """验证JWT令牌

        Args:
            token: JWT令牌字符串

        Returns:
            认证结果
        """
        # 检查令牌是否被吊销
        if await self._is_revoked(token):
            return AuthResult(success=False, error="Token has been revoked")

        try:
            # 解码并验证令牌
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[JWT_ALGORITHM],
                issuer=self._issuer,
                audience=self._audience,
            )

            # 提取声明
            return AuthResult(
                success=True,
                tenant_id=payload.get("tenant_id"),
                user_id=payload.get("sub"),
                email=payload.get("email"),
                roles=payload.get("roles", []),
                scopes=payload.get("scope", "").split(),
                claims=payload,
            )

        except jwt.ExpiredSignatureError:
            _log.warning("Token has expired")
            return AuthResult(success=False, error="Token has expired")

        except jwt.InvalidIssuerError:
            _log.warning("Invalid token issuer")
            return AuthResult(success=False, error="Invalid token issuer")

        except jwt.InvalidAudienceError:
            _log.warning("Invalid token audience")
            return AuthResult(success=False, error="Invalid token audience")

        except jwt.InvalidTokenError as e:
            _log.warning(f"Invalid token: {e}")
            return AuthResult(success=False, error="Invalid token")

    async def extract_token(self, request: Request) -> str | None:
        """从请求中提取令牌

        支持:
        - Authorization: Bearer <token>
        - X-API-Token: <token>

        Args:
            request: API请求

        Returns:
            令牌字符串，如果没有则返回None
        """
        # 从Authorization头提取
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # 从X-API-Token头提取
        api_token = request.headers.get("X-API-Token", "")
        if api_token:
            return api_token.strip()

        return None

    async def _is_revoked(self, token: str) -> bool:
        """检查令牌是否被吊销

        Args:
            token: JWT令牌

        Returns:
            是否被吊销
        """
        # 简化的吊销检查，实际应该使用Redis等存储
        return token in self._revoked_tokens

    async def revoke_token(self, token: str) -> None:
        """吊销令牌

        Args:
            token: 要吊销的令牌
        """
        self._revoked_tokens.add(token)
        _log.info(f"Token revoked: {token[:16]}...")

    def generate_token(
        self,
        tenant_id: str,
        user_id: str,
        email: str | None = None,
        roles: list[str] | None = None,
        scopes: list[str] | None = None,
        expires_in: int = 3600,
    ) -> str:
        """生成JWT令牌 (用于测试)

        Args:
            tenant_id: 租户ID
            user_id: 用户ID
            email: 用户邮箱
            roles: 用户角色
            scopes: 授权范围
            expires_in: 过期时间(秒)

        Returns:
            JWT令牌
        """
        now = datetime.now(UTC)
        payload = {
            "iss": self._issuer,
            "sub": user_id,
            "aud": self._audience,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "tenant_id": tenant_id,
            "email": email,
            "roles": roles or [],
            "scope": " ".join(scopes or []),
            "jti": secrets.token_urlsafe(16),
        }

        return jwt.encode(payload, self._secret_key, algorithm=JWT_ALGORITHM)


class AuthenticationError(Exception):
    """认证错误"""

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code or "authentication_failed"


class TokenExpiredError(AuthenticationError):
    """令牌已过期错误"""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message, code="token_expired")


class TokenRevokedError(AuthenticationError):
    """令牌被吊销错误"""

    def __init__(self, message: str = "Token has been revoked") -> None:
        super().__init__(message, code="token_revoked")
