from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class PositionTemplateCreate(BaseModel):
    position_tag: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    category: Literal["backend", "frontend", "ai", "mobile", "devops"]
    level: Literal["intern", "junior", "mid", "senior"] = "junior"
    core_skills: List[str]
    nice_to_have_skills: List[str]
    project_keywords: List[str]
    focus_topics: List[str]
    recommended_query_keywords: List[str]
    recommended_difficulty: Literal["easy", "medium", "hard"] = "medium"
    recommended_question_count: int = Field(8, ge=1, le=30)
    jd_summary: Optional[str] = None
    typical_companies: List[str]
    sort_order: int = Field(0, ge=0)
    is_active: bool = True


class PositionTemplateUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    category: Optional[Literal["backend", "frontend", "ai", "mobile", "devops"]] = None
    level: Optional[Literal["intern", "junior", "mid", "senior"]] = None
    core_skills: Optional[List[str]] = None
    nice_to_have_skills: Optional[List[str]] = None
    project_keywords: Optional[List[str]] = None
    focus_topics: Optional[List[str]] = None
    recommended_query_keywords: Optional[List[str]] = None
    recommended_difficulty: Optional[Literal["easy", "medium", "hard"]] = None
    recommended_question_count: Optional[int] = Field(None, ge=1, le=30)
    jd_summary: Optional[str] = None
    typical_companies: Optional[List[str]] = None
    sort_order: Optional[int] = Field(None, ge=0)

class PositionTemplateToggle(BaseModel):
    is_active: bool

    