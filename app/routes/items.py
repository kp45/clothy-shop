from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import json

from app.database.db import get_db
from app.models.models import Item, ItemMatching

router = APIRouter(prefix="/items", tags=["Items"])


def _safe_json_list(raw_value: Optional[str]) -> list:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _normalize_matching_ids(values: list) -> list:
    normalized = []
    for value in values:
        if not isinstance(value, str):
            continue
        clean = value.strip()
        if clean:
            normalized.append(clean)
    return normalized[:3]


def _matching_row_to_list(row: Optional[ItemMatching]) -> list:
    if not row:
        return []
    return _normalize_matching_ids([row.match_1, row.match_2, row.match_3])


def _matching_columns(values: list) -> tuple[str, str, str]:
    cleaned = _normalize_matching_ids(values)
    padded = (cleaned + ["", "", ""])[:3]
    return padded[0], padded[1], padded[2]


def _serialize_item(item: Item, matching_row: Optional[ItemMatching] = None):
    variants = _safe_json_list(item.variants)
    related_items = _matching_row_to_list(matching_row)
    if not related_items:
        # Backward-compatible fallback for old rows that used items.related_items.
        related_items = _normalize_matching_ids(_safe_json_list(item.related_items))

    return ItemOut(
        id=item.id,
        unique_id=item.unique_id,
        title=item.title,
        image_url=item.image_url,
        price=item.price,
        category=item.category,
        description=item.description,
        variants=variants,
        related_items=related_items,
        is_active=item.is_active,
    )


# ---------- Schemas ----------
class ItemCreate(BaseModel):
    unique_id: str
    title: str
    image_url: str
    price: float = 0.0
    category: str = ""
    description: str = ""
    variants: list = []
    related_items: list = []


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    image_url: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    variants: Optional[list] = None
    related_items: Optional[list] = None
    is_active: Optional[bool] = None


class ItemOut(BaseModel):
    id: int
    unique_id: str
    title: str
    image_url: str
    price: float
    category: str
    description: str
    variants: list
    related_items: list
    is_active: bool

    class Config:
        from_attributes = True


# ---------- Routes ----------
@router.get("/", response_model=List[ItemOut])
def get_all_items(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    items = db.query(Item).filter(Item.is_active == True).offset(skip).limit(limit).all()
    if not items:
        return []

    item_ids = [item.unique_id for item in items]
    matching_rows = db.query(ItemMatching).filter(ItemMatching.item_unique_id.in_(item_ids)).all()
    matching_map = {row.item_unique_id: row for row in matching_rows}

    return [_serialize_item(item, matching_map.get(item.unique_id)) for item in items]


@router.get("/{unique_id}", response_model=ItemOut)
def get_item(unique_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.unique_id == unique_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    matching_row = db.query(ItemMatching).filter(ItemMatching.item_unique_id == unique_id).first()
    return _serialize_item(item, matching_row)


@router.post("/", response_model=ItemOut, status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    existing = db.query(Item).filter(Item.unique_id == payload.unique_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="unique_id already exists")

    normalized_related = _normalize_matching_ids(payload.related_items)
    m1, m2, m3 = _matching_columns(normalized_related)

    item = Item(
        **payload.dict(exclude={"variants", "related_items"}),
        variants=json.dumps(payload.variants),
        related_items=json.dumps(normalized_related),
    )
    db.add(item)
    db.flush()

    matching_row = db.query(ItemMatching).filter(
        ItemMatching.item_unique_id == payload.unique_id
    ).first()
    if not matching_row:
        matching_row = ItemMatching(item_unique_id=payload.unique_id)
        db.add(matching_row)

    matching_row.match_1 = m1
    matching_row.match_2 = m2
    matching_row.match_3 = m3

    db.commit()
    db.refresh(item)
    db.refresh(matching_row)
    return _serialize_item(item, matching_row)


@router.put("/{unique_id}", response_model=ItemOut)
def update_item(unique_id: str, payload: ItemUpdate, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.unique_id == unique_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    data = payload.dict(exclude_unset=True)
    related_for_matching = None

    if "variants" in data:
        data["variants"] = json.dumps(data["variants"])

    if "related_items" in data:
        related_for_matching = _normalize_matching_ids(data.pop("related_items"))
        # Keep legacy column synced for backward compatibility.
        data["related_items"] = json.dumps(related_for_matching)

    for key, value in data.items():
        setattr(item, key, value)

    matching_row = db.query(ItemMatching).filter(ItemMatching.item_unique_id == unique_id).first()
    if related_for_matching is not None:
        if not matching_row:
            matching_row = ItemMatching(item_unique_id=unique_id)
            db.add(matching_row)
        m1, m2, m3 = _matching_columns(related_for_matching)
        matching_row.match_1 = m1
        matching_row.match_2 = m2
        matching_row.match_3 = m3

    db.commit()
    db.refresh(item)
    if not matching_row:
        matching_row = db.query(ItemMatching).filter(ItemMatching.item_unique_id == unique_id).first()
    elif matching_row.id:
        db.refresh(matching_row)

    return _serialize_item(item, matching_row)


@router.delete("/{unique_id}")
def delete_item(unique_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.unique_id == unique_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    matching_row = db.query(ItemMatching).filter(ItemMatching.item_unique_id == unique_id).first()
    if matching_row:
        db.delete(matching_row)

    db.delete(item)
    db.commit()
    return {"message": f"Item {unique_id} deleted"}
