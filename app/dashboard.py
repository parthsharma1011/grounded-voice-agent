from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from livekit import api
from pydantic import BaseModel, Field

from app.dispatch import dispatch_call
from personas import registry

load_dotenv()

DEFAULT_COUNTRY_CODE = os.environ.get("DEFAULT_COUNTRY_CODE", "49")
HERE = Path(__file__).parent

ALLOWED_PREFIXES = {
    "+49": "Germany",
    "+43": "Austria",
    "+41": "Switzerland",
    "+44": "United Kingdom",
    "+1": "US/Canada",
    "+91": "India",
}

app = FastAPI(title="Voice Agent Dashboard")


class CallRequest(BaseModel):
    industry: str
    phone_number: str = Field(min_length=5)
    caller_name: str = ""


def normalise(raw: str) -> str:
    cleaned = re.sub(r"[\s\-().]", "", raw.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    elif cleaned.startswith("0"):
        cleaned = "+" + DEFAULT_COUNTRY_CODE + cleaned[1:]
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    if not re.fullmatch(r"\+\d{7,15}", cleaned):
        raise HTTPException(400, f"'{raw}' is not a valid international number.")
    return cleaned


def country_of(number: str) -> str:
    for prefix in sorted(ALLOWED_PREFIXES, key=len, reverse=True):
        if number.startswith(prefix):
            return ALLOWED_PREFIXES[prefix]
    raise HTTPException(
        400,
        f"Calls to {number} are not enabled on the Twilio trunk. "
        f"Enabled: {', '.join(ALLOWED_PREFIXES.values())}.",
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(HERE / "dashboard.html", headers={"Cache-Control": "no-store"})


@app.get("/api/livereload")
async def livereload() -> StreamingResponse:
    path = HERE / "dashboard.html"

    async def events():
        last = path.stat().st_mtime
        while True:
            await asyncio.sleep(0.5)
            try:
                now = path.stat().st_mtime
            except FileNotFoundError:
                continue
            if now != last:
                last = now
                yield "data: reload\n\n"
            else:
                yield ": keepalive\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/industries")
async def industries() -> list[dict]:
    return [
        {"key": p.key, "label": p.label, "blurb": p.blurb, "agent": p.agent_display_name}
        for p in registry.PERSONAS.values()
    ]


@app.get("/api/status")
async def status() -> dict:
    trunk_id = os.environ.get("SIP_OUTBOUND_TRUNK_ID", "")
    lk = api.LiveKitAPI()
    try:
        workers_ok = True
        try:
            await lk.room.list_rooms(api.ListRoomsRequest())
        except Exception:
            workers_ok = False
        return {
            "trunk_configured": bool(trunk_id),
            "trunk_id": trunk_id,
            "livekit_reachable": workers_ok,
            "caller_id": os.environ.get("TWILIO_PHONE_NUMBER", ""),
        }
    finally:
        await lk.aclose()


@app.post("/api/call")
async def place_call(req: CallRequest) -> dict:
    if req.industry not in registry.PERSONAS:
        raise HTTPException(400, f"Unknown industry '{req.industry}'.")
    if not os.environ.get("SIP_OUTBOUND_TRUNK_ID"):
        raise HTTPException(500, "SIP_OUTBOUND_TRUNK_ID is not set. Run python -m app.provision.")

    number = normalise(req.phone_number)
    country = country_of(number)
    persona = registry.PERSONAS[req.industry]

    lk_check = api.LiveKitAPI()
    try:
        rooms = await lk_check.room.list_rooms(api.ListRoomsRequest())
        suffix = number.lstrip("+")
        for r in rooms.rooms:
            if suffix in r.name and r.num_participants > 0:
                raise HTTPException(
                    409, f"A call to {number} is already in progress. Hang up first."
                )
    finally:
        await lk_check.aclose()

    try:
        room, dispatch = await dispatch_call(req.industry, number, req.caller_name or "the caller")
    except Exception as e:
        raise HTTPException(502, f"Dispatch failed: {e}") from e

    return {
        "ok": True,
        "room": room,
        "dispatch_id": dispatch.id,
        "calling": number,
        "country": country,
        "agent": persona.agent_display_name,
        "industry": persona.label,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
