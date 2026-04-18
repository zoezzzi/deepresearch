from typing import TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseCRUD:
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get_by_id(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.get(self.model, id)

    def list(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        result = db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        obj_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else dict(obj_in)
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        obj_data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else dict(obj_in)
        for field, value in obj_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: Any) -> bool:
        result = db.execute(delete(self.model).where(self.model.id == id))
        db.commit()
        return result.rowcount > 0
