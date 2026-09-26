from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

class ApiResponse:
    """API响应处理类"""

    @staticmethod
    def success(
            data=None,
            message: str = "Success",
            body_code: int = 200,
            http_code: int = status.HTTP_200_OK,
    ) -> JSONResponse:
        """成功响应"""
        response_data = {
            "code": body_code,
            "message": message,
            "data": jsonable_encoder(data) if data is not None else None,
        }
        return JSONResponse(content=response_data, status_code=http_code)

    @staticmethod
    def failed(
            message: str,
            body_code: int,
            http_code: int = status.HTTP_400_BAD_REQUEST,
            data=None,
    ) -> JSONResponse:
        """失败响应"""
        response_data = {
            "code": body_code,
            "message": message,
        }
        if data is not None:
            response_data["data"] = jsonable_encoder(data)
        return JSONResponse(content=response_data, status_code=http_code)