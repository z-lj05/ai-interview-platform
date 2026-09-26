from .base import BaseModel
from sqlalchemy import Column, Integer, String, Boolean


class Admin(BaseModel):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)