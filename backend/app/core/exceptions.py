"""应用自定义异常层次结构。

每个异常携带一个数字错误码 ``code``（用于 API 响应）、``message`` 和
HTTP ``status_code``。错误码约定：HTTP 状态码后跟两位序号（如 40400 表示第一个 404 错误）。
"""


class AppException(Exception):
    def __init__(self, message: str = "", code: int = 40000, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFound(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=40400, message=message, status_code=404)


class Unauthorized(AppException):
    def __init__(self, message: str = "未登录或 token 已过期"):
        super().__init__(code=40100, message=message, status_code=401)


class Forbidden(AppException):
    def __init__(self, message: str = "权限不足"):
        super().__init__(code=40300, message=message, status_code=403)


class BadRequest(AppException):
    def __init__(self, message: str = "请求参数错误", code: int = 40000):
        super().__init__(code=code, message=message, status_code=400)
