from fastapi import HTTPException
from typing import Any


class APIException(HTTPException):
    """业务异常基类"""

    def __init__(
          self,
          code: int = 10000,
          message: str = "API 异常",
          status_code: int = 400,
          data: Any = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)

        self.code = code  # ② 业务错误码
        self.data = data  # ③ 额外数据


class NotFoundError(APIException):
    """资源不存在"""
    def __init__(self, message: str = "资源不存在", data: Any = None):
         super().__init__(code=1004, message=message, status_code=404, data=data)  # ④


class AuthenticationError(APIException):
    """认证失败"""
    def __init__(self, message: str = "认证失败", data: Any = None):
         super().__init__(code=1002, message=message, status_code=401, data=data)  # 5


class ValidationError(APIException):
    """参数验证错误"""
    def __init__(self, message: str = "参数验证错误", data: Any = None):
        super().__init__(code=1001, message=message, status_code=400, data=data)