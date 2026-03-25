from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.database.db import Base

class Item(Base):
    __tablename__ = "items"

    id          = Column(Integer, primary_key=True, index=True)
    unique_id   = Column(String, unique=True, index=True, nullable=False)
    title       = Column(String, nullable=False)
    image_url   = Column(String, nullable=False)
    price       = Column(Float, default=0.0)
    category    = Column(String, default="")
    description = Column(Text, default="")
    variants    = Column(Text, default="[]")   # JSON string list of variant URLs/names
    related_items = Column(Text, default="[]") # JSON string list of related item unique_ids
    is_active   = Column(Boolean, default=True)


class Catalog(Base):
    __tablename__ = "catalog"

    id             = Column(Integer, primary_key=True, index=True)
    item_unique_id = Column(String, nullable=False)   # references Item.unique_id
    position       = Column(Integer, default=0)        # order in the banner


class TestimonialImage(Base):
    __tablename__ = "testimonials"

    id        = Column(Integer, primary_key=True, index=True)
    image_url = Column(String, nullable=False)
    position  = Column(Integer, default=0)


class ItemMatching(Base):
    __tablename__ = "item_matching"

    id             = Column(Integer, primary_key=True, index=True)
    item_unique_id = Column(String, unique=True, index=True, nullable=False)
    match_1        = Column(String, default="")
    match_2        = Column(String, default="")
    match_3        = Column(String, default="")
