class AppException(Exception):
    """应用异常基类。"""
    status_code: int = 500
    detail: str = "服务器内部错误"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class Unauthorized(AppException):
    status_code = 401
    detail = "未认证或认证已过期"


class Forbidden(AppException):
    status_code = 403
    detail = "无权限访问"


class NotFound(AppException):
    status_code = 404
    detail = "资源不存在"


class Conflict(AppException):
    status_code = 409
    detail = "资源冲突"


class InternalError(AppException):
    status_code = 500
    detail = "服务器内部错误"


class UserNotFound(NotFound):
    detail = "用户不存在"


class KnowledgeBaseNotFound(NotFound):
    detail = "知识库不存在"


class SessionNotFound(NotFound):
    detail = "聊天会话不存在"


class WrongCredentials(Unauthorized):
    detail = "用户名或密码错误"


class TokenRevoked(Unauthorized):
    detail = "Token 已注销"


class UserAlreadyExists(Conflict):
    detail = "用户名已存在"


class KnowledgeBaseAlreadyExists(Conflict):
    detail = "知识库已存在"


class DatabaseError(InternalError):
    detail = "数据库异常，请稍后重试"
