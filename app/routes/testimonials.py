from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database.db import get_db
from app.models.models import TestimonialImage

router = APIRouter(prefix="/testimonials", tags=["Testimonials"])


class TestimonialCreate(BaseModel):
    image_url: str
    position: int = 0


class TestimonialOut(BaseModel):
    id: int
    image_url: str
    position: int

    class Config:
        from_attributes = True


@router.get("/", response_model=List[TestimonialOut])
def get_testimonials(db: Session = Depends(get_db)):
    return db.query(TestimonialImage).order_by(TestimonialImage.position, TestimonialImage.id).all()


@router.post("/", response_model=TestimonialOut, status_code=201)
def create_testimonial(payload: TestimonialCreate, db: Session = Depends(get_db)):
    entry = TestimonialImage(**payload.dict())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{testimonial_id}")
def delete_testimonial(testimonial_id: int, db: Session = Depends(get_db)):
    entry = db.query(TestimonialImage).filter(TestimonialImage.id == testimonial_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Testimonial image not found")
    db.delete(entry)
    db.commit()
    return {"message": f"Testimonial image {testimonial_id} deleted"}
