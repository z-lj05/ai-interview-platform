from sqlalchemy import Column, Integer, String, Boolean
from .base import BaseModel

class User(BaseModel):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)