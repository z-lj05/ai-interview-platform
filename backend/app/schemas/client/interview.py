from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class InterviewStart(BaseModel):
    resume_id: int
    target_position: str = "Python后端开发工程师"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    total_questions: int = Field(default=5, ge=3, le=10)


class AnswerSubmit(BaseModel):
    answer: str = Field(..., min_length=1, max_length=5000)


class InterviewReport(BaseModel):
    interview_id: int
    overall_score: float
    total_questions: int
    report: Dict[str, Any]


class InterviewListItem(BaseModel):
    interview_id: int
    target_position: str
    difficulty: str
    overall_score: Optional[float] = None
    total_questions: int
    status: str
    created_at: Optional[str] = None
