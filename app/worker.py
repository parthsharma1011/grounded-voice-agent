from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
from livekit import agents, api
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    inference,
    room_io,
)
from livekit.agents.voice.amd import AMD, AMDCategory
from livekit.agents.voice.turn import EndpointingOptions, InterruptionOptions
from livekit.plugins import noise_cancellation, silero

from app.dispatch import AGENT_NAME
from personas import registry

load_dotenv()

logger = logging.getLogger("voice-agent")

OUTBOUND_TRUNK_ID = os.environ.get("SIP_OUTBOUND_TRUNK_ID", "")
CALLER_IDENTITY = "phone_caller"

AMD_MODEL = os.environ.get("AMD_MODEL", "google/gemini-2.5-flash-lite")
LEAVE_VOICEMAIL = os.environ.get("LEAVE_VOICEMAIL", "true").lower() == "true"

STT_MODEL = os.environ.get("STT_MODEL", "deepgram/nova-3")
LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4.1-mini")
TTS_MODEL = os.environ.get("TTS_MODEL", "cartesia/sonic-3.5")
TTS_VOICE = os.environ.get("TTS_VOICE", "")
TTS_FALLBACKS = [
    m.strip()
    for m in os.environ.get("TTS_FALLBACKS", "cartesia/sonic-2,inworld/inworld-tts-1.5").split(",")
    if m.strip()
]

server = AgentServer()


async def hangup(ctx: JobContext) -> None:
    await ctx.api.room.delete_room(api.DeleteRoomRequest(room=ctx.room.name))


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    meta = json.loads(ctx.job.metadata or "{}")
    phone_number = meta.get("phone_number")
    caller_name = meta.get("caller_name") or "the caller"
    persona = registry.get(meta.get("industry"))

    ctx.log_context_fields = {
        "room": ctx.room.name,
        "persona": persona.key,
        "phone": phone_number,
    }

    session = AgentSession(
        stt=inference.STT(model=STT_MODEL, language="multi"),
        vad=silero.VAD.load(
            min_speech_duration=0.20,
            min_silence_duration=0.55,
            activation_threshold=0.55,
        ),
        llm=inference.LLM(model=LLM_MODEL),
        tts=inference.TTS(
            model=TTS_MODEL,
            language="de",
            fallback=TTS_FALLBACKS,
            **({"voice": TTS_VOICE} if TTS_VOICE else {}),
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            interruption=InterruptionOptions(
                min_duration=0.7,
                min_words=2,
                resume_false_interruption=True,
                false_interruption_timeout=2.0,
            ),
            endpointing=EndpointingOptions(min_delay=0.6, max_delay=4.0),
        ),
    )

    await session.start(
        persona.agent_cls(caller_name),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVCTelephony(),
                auto_gain_control=True,
            ),
        ),
    )

    if not phone_number:
        await session.generate_reply(instructions=persona.greeting)
        return

    if not OUTBOUND_TRUNK_ID:
        raise RuntimeError("SIP_OUTBOUND_TRUNK_ID is not set. Run python -m app.provision first")

    try:
        async with AMD(
            session,
            llm=AMD_MODEL,
            participant_identity=CALLER_IDENTITY,
            interrupt_on_machine=True,
        ) as detector:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=OUTBOUND_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=CALLER_IDENTITY,
                    participant_name=caller_name,
                    wait_until_answered=True,
                    krisp_enabled=True,
                )
            )
            session.generate_reply(instructions=persona.greeting)
            verdict = await detector.execute()
    except api.TwirpError as e:
        logger.error(
            "call failed: %s | sip_status=%s %s",
            e.message,
            e.metadata.get("sip_status_code"),
            e.metadata.get("sip_status"),
        )
        ctx.shutdown()
        return

    logger.info(
        "AMD verdict=%s (%s) after %.1fs: %r",
        verdict.category.value, verdict.reason, verdict.speech_duration, verdict.transcript[:80],
    )

    if verdict.is_machine:
        if verdict.category is AMDCategory.MACHINE_VM and LEAVE_VOICEMAIL:
            logger.info("voicemail, leaving a message")
            await session.say(persona.voicemail, allow_interruptions=False)
        else:
            logger.info("machine (%s), hanging up", verdict.category.value)
        await hangup(ctx)
        return

    logger.info("human, %s is live", persona.agent_display_name)


if __name__ == "__main__":
    agents.cli.run_app(server)
