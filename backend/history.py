"""
Saved-debate history, backed by Supabase Postgres. Uses the service_role key
(server-side only, bypasses Row Level Security) since the backend has already
verified the caller's identity via get_current_user — every query still
filters by user_id explicitly as defense-in-depth, RLS bypass or not.
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client, create_client

from backend.auth import get_current_user

router = APIRouter()

_client: Client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise HTTPException(500, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
        _client = create_client(url, key)
    return _client


class SaveDebateRequest(BaseModel):
    ticker: str
    market: Optional[str] = None
    cio_memo: str
    stage1: dict
    debate: list


@router.post("/history")
def save_debate(req: SaveDebateRequest, user_id: str = Depends(get_current_user)):
    row = {
        "user_id": user_id,
        "ticker": req.ticker.upper(),
        "market": req.market,
        "cio_memo": req.cio_memo,
        "stage1": req.stage1,
        "debate": req.debate,
    }
    result = _get_client().table("saved_debates").insert(row).execute()
    return result.data[0]


@router.get("/history")
def list_history(user_id: str = Depends(get_current_user)):
    result = (
        _get_client()
        .table("saved_debates")
        .select("id,ticker,market,cio_memo,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/history/{entry_id}")
def get_history_entry(entry_id: str, user_id: str = Depends(get_current_user)):
    result = (
        _get_client()
        .table("saved_debates")
        .select("*")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Not found")
    return result.data[0]


@router.delete("/history/{entry_id}")
def delete_history_entry(entry_id: str, user_id: str = Depends(get_current_user)):
    _get_client().table("saved_debates").delete().eq("id", entry_id).eq("user_id", user_id).execute()
    return {"deleted": True}
