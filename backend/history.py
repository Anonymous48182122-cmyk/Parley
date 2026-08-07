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
    user_chat: Optional[list] = None
    cross_exams: Optional[dict] = None
    market_data: Optional[dict] = None


@router.post("/history")
def save_debate(req: SaveDebateRequest, user_id: str = Depends(get_current_user)):
    row = {
        "user_id": user_id,
        "ticker": req.ticker.upper(),
        "market": req.market,
        "cio_memo": req.cio_memo,
        "stage1": req.stage1,
        "debate": req.debate,
        "user_chat": req.user_chat or [],
        "cross_exams": req.cross_exams or {},
        "market_data": req.market_data or {},
    }
    result = _get_client().table("saved_debates").insert(row).execute()
    return result.data[0]


HISTORY_EXCERPT_LEN = 300


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
    # The list view only ever renders a ~140-char excerpt (see HistoryPage.jsx)
    # — truncate here so a user with several saved debates isn't shipped
    # several KB of full memo text per row just to throw most of it away
    # client-side. The full text is still fetched in full on /history/{id}.
    rows = result.data
    for row in rows:
        memo = row.get("cio_memo") or ""
        row["cio_memo"] = memo[:HISTORY_EXCERPT_LEN]
    return rows


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
