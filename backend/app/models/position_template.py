from .base import BaseModel
from sqlalchemy import Column, Integer, String, Boolean, JSON, Text

class PositionTemplate(BaseModel):
    __tablename__ = 'positions'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    position_tag = Column(String(100), unique=True, index=True, nullable=False) # 代号
    title = Column(String(200), nullable=False) # 展示名
    category = Column(String(50), nullable=False) # 大类
    level = Column(String, nullable=False, default="junior") # 级别
    core_skills = Column(JSON, nullable=False) # 核心技能
    nice_to_have_skills = Column(JSON, nullable=False) # 加分技能
    project_keywords = Column(JSON, nullable=False) # 项目关键词
    focus_topics = Column(JSON, nullable=False) # 面试重点
    recommended_query_keywords = Column(JSON, nullable=False) # 题库 RAG 检索关键词
    recommended_difficulty = Column(String(255), nullable=False, default="medium") # 出题难度
    recommended_question_count = Column(Integer, nullable=False, default=8) # 出题数量
    jd_summary = Column(Text, nullable=True) # 岗位职责/JD 摘要
    typical_companies = Column(JSON, nullable=False) # 典型公司
    sort_order = Column(Integer, index=True, default=0) # 排序
    is_active = Column(Boolean, index=True, default=True) # 下架开关