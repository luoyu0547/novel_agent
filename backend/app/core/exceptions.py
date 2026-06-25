class AppException(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400):
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
    def __init__(self, code: int = 40000, message: str = "请求参数错误"):
        super().__init__(code=code, message=message, status_code=400)
