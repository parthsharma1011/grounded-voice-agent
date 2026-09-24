from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

from app.dispatch import dispatch_call
from personas import registry

load_dotenv()


async def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(
            "usage: uv run python -m app.dial +49XXXXXXXXXX [industry] [\"Name\"]\n"
            f"industries: {', '.join(registry.PERSONAS)}"
        )

    phone_number = sys.argv[1].strip()
    industry = sys.argv[2] if len(sys.argv) > 2 else registry.DEFAULT_PERSONA
    caller_name = sys.argv[3] if len(sys.argv) > 3 else "the caller"

    if not phone_number.startswith("+"):
        sys.exit("Number must be E.164, e.g. +4915112345678")
    if industry not in registry.PERSONAS:
        sys.exit(f"Unknown industry '{industry}'. Options: {', '.join(registry.PERSONAS)}")
    if not os.environ.get("SIP_OUTBOUND_TRUNK_ID"):
        sys.exit("SIP_OUTBOUND_TRUNK_ID is not set. Run python -m app.provision first")

    persona = registry.PERSONAS[industry]
    room, _ = await dispatch_call(industry, phone_number, caller_name)
    print(f"{persona.agent_display_name} ({persona.label}) is calling {phone_number}")
    print(f"room: {room}")


if __name__ == "__main__":
    asyncio.run(main())
