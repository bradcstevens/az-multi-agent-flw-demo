from fastapi import APIRouter, Depends, HTTPException


api_v3 = APIRouter(
    prefix="/v3",
    responses={404: {"description": "Not found"}},
)

fake_items_db = {"plumbus": {"name": "Plumbus"}, "gun": {"name": "Portal Gun"}}


@api_v3.get("/")
async def read_items():
    return fake_items_db
