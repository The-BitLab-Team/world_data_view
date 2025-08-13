# main.py
# Ponto de entrada do backend (FastAPI)

from fastapi import FastAPI
from app.api import endpoints


app = FastAPI()
app.include_router(endpoints.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "World Data View API"}
