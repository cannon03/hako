from pydantic import BaseModel,ConfigDict   
from datetime import datetime

class BucketResponse(BaseModel):
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ObjectResponse(BaseModel):
    key: str
    size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
