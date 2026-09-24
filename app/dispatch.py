from __future__ import annotations

import json
import os

from livekit import api

AGENT_NAME = "realestate-agent"


async def dispatch_call(industry: str, phone_number: str, caller_name: str) -> tuple[str, api.AgentDispatch]:
    room = f"{industry}-{phone_number.lstrip('+')}-{os.urandom(3).hex()}"
    lk = api.LiveKitAPI()
    try:
        dispatch = await lk.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room,
                metadata=json.dumps(
                    {
                        "phone_number": phone_number,
                        "caller_name": caller_name,
                        "industry": industry,
                    }
                ),
            )
        )
    finally:
        await lk.aclose()
    return room, dispatch
