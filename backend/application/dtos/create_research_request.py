from pydantic import BaseModel, Field, validator
from typing import Optional


class CreateResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="调研主题")
    description: Optional[str] = Field(None, description="调研描述")
    
    @validator('topic', pre=True)
    def validate_topic(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ''):
            raise ValueError('Topic cannot be empty')
        return v.strip() if isinstance(v, str) else v
