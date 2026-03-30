from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # kept for any legacy static assets
from sqlalchemy import text
import os

from app.database.db import SessionLocal, engine
from app.models.models import Base, Item, ItemMatching
from app.routes import items, catalog, upload, testimonials

# Create all tables on startup
Base.metadata.create_all(bind=engine)
with engine.begin() as connection:
    connection.execute(
        text("ALTER TABLE items ADD COLUMN IF NOT EXISTS related_items TEXT DEFAULT '[]'")
    )


def ensure_item_matching_seed_data():
    db = SessionLocal()
    try:
        # Ensure each existing item has a matching row initialized with empty values.
        existing = {
            row.item_unique_id
            for row in db.query(ItemMatching.item_unique_id).all()
        }
        for (unique_id,) in db.query(Item.unique_id).all():
            if unique_id not in existing:
                db.add(ItemMatching(item_unique_id=unique_id, match_1="", match_2="", match_3=""))

        # Test seed requested: id001 -> id001,id001,id001
        seed_key = "id001"
        seed_row = db.query(ItemMatching).filter(ItemMatching.item_unique_id == seed_key).first()
        if not seed_row:
            seed_row = ItemMatching(item_unique_id=seed_key)
            db.add(seed_row)
        if not (seed_row.match_1 or seed_row.match_2 or seed_row.match_3):
            seed_row.match_1 = seed_key
            seed_row.match_2 = seed_key
            seed_row.match_3 = seed_key

        # Convenience seed for current sample dataset (item001) without overriding existing data.
        sample_key = "item001"
        sample_row = db.query(ItemMatching).filter(ItemMatching.item_unique_id == sample_key).first()
        if sample_row and not (sample_row.match_1 or sample_row.match_2 or sample_row.match_3):
            sample_row.match_1 = sample_key
            sample_row.match_2 = sample_key
            sample_row.match_3 = sample_key

        db.commit()
    finally:
        db.close()


ensure_item_matching_seed_data()

app = FastAPI(title="Clothy API", version="1.0.0")

# Allow React Native dev client + Expo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(items.router)
app.include_router(catalog.router)
app.include_router(upload.router)
app.include_router(testimonials.router)

@app.get("/")
def root():
    return {"message": "Clothy API is running 🧵"}
