from fastapi import FastAPI
from sqlmodel import Session, text
from app.db import engine

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health/db")
def health_db():
    with Session(engine) as session:
        result = session.exec(text("SELECT 1")).scalar_one()
        return {"db": result}
