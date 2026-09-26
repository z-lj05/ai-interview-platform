from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.schemas.response import ApiResponse
from app.exceptions.http_exceptions import APIException, AuthenticationError, NotFoundError
from app.api.client.v1.auth import router as auth_router
from app.api.client.v1.resume import router as resume_router
from app.api.backoffice.v1.auth import router as auth_backoffice_router
from app.api.backoffice.v1.position_templates import router as position_template_router
from app.api.client.v1.position_agent import router as position_agent_router
from app.api.backoffice.v1.question_bank import router as question_bank_router
from app.api.backoffice.v1.users import router as users_router
from app.api.backoffice.v1.interviews import router as interviews_admin_router
from app.api.backoffice.v1.knowledge import router as knowledge_router
from app.api.client.v1.interview import router as interview_router
from app.api.client.v1.waiting_list import router as waiting_list_router
from app.api.client.v1.config import router as config_router

app = FastAPI()

@app.get("/")
async def hello():
    return ApiResponse.success(data={"message": "hello"})

@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return ApiResponse.failed(
        message=exc.detail,
        body_code=exc.code,
        http_code=exc.status_code,
        data=exc.data,
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return ApiResponse.failed(
        message=exc.detail,
        body_code=exc.status_code,
        http_code=exc.status_code,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return ApiResponse.failed(
        message="参数验证错误",
        body_code=1001,
        http_code=400,
        data=exc.errors(),
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return ApiResponse.failed(
        message="服务器内部错误",
        body_code=1005,
        http_code=500,
    )

app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth")
app.include_router(resume_router, prefix=f"{settings.API_V1_STR}/resumes")
app.include_router(auth_backoffice_router, prefix=f"{settings.API_V1_STR}/backoffice/auth")
app.include_router(position_template_router, prefix=f"{settings.API_V1_STR}/backoffice/position-templates")
app.include_router(position_agent_router, prefix=f"{settings.API_V1_STR}/position-agent")
app.include_router(question_bank_router, prefix=f"{settings.API_V1_STR}/backoffice/question-bank")
app.include_router(users_router, prefix=f"{settings.API_V1_STR}/backoffice/users")
app.include_router(interviews_admin_router, prefix=f"{settings.API_V1_STR}/backoffice/interviews")
app.include_router(knowledge_router, prefix=f"{settings.API_V1_STR}/backoffice/knowledge")
app.include_router(interview_router, prefix=f"{settings.API_V1_STR}/interviews")
app.include_router(waiting_list_router, prefix=f"{settings.API_V1_STR}/waiting-list")
app.include_router(config_router, prefix=f"{settings.API_V1_STR}/config")

if __name__ == "__main__":
    import uvicorn

    # host 必须是 0.0.0.0：容器内监听 0.0.0.0 端口映射才生效，
    # 写 127.0.0.1 只有容器自己访问得到。本地开发两者皆可。
    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)