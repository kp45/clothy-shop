from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database.db import get_db
from app.models.models import Catalog, Item

router = APIRouter(prefix="/catalog", tags=["Catalog"])

class CatalogEntry(BaseModel):
    item_unique_id: str
    position: int = 0

class CatalogOut(BaseModel):
    id: int
    item_unique_id: str
    position: int
    title: str
    image_url: str

    class Config:
        from_attributes = True

@router.get("/", response_model=List[CatalogOut])
def get_catalog(db: Session = Depends(get_db)):
    entries = db.query(Catalog).order_by(Catalog.position).all()
    result = []
    for e in entries:
        item = db.query(Item).filter(Item.unique_id == e.item_unique_id).first()
        if item:
            result.append(CatalogOut(
                id=e.id,
                item_unique_id=e.item_unique_id,
                position=e.position,
                title=item.title,
                image_url=item.image_url,
            ))
    return result

@router.post("/", status_code=201)
def add_to_catalog(payload: CatalogEntry, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.unique_id == payload.item_unique_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    entry = Catalog(**payload.dict())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"message": "Added to catalog", "id": entry.id}

@router.delete("/{item_unique_id}")
def remove_from_catalog(item_unique_id: str, db: Session = Depends(get_db)):
    entry = db.query(Catalog).filter(Catalog.item_unique_id == item_unique_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not in catalog")
    db.delete(entry)
    db.commit()
    return {"message": f"{item_unique_id} removed from catalog"}
