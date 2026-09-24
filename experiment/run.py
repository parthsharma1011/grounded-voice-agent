from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from livekit.agents import ChatContext, inference
from livekit.agents.llm import FunctionCall, FunctionCallOutput
from pydantic import BaseModel

from experiment import datasets
from experiment.scorer import score_after, score_before
from personas.healthcare import HealthcareAgent
from personas.real_estate import RealEstateAgent
from personas.restaurant import RestaurantAgent

load_dotenv(datasets.ROOT / ".env")

LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4.1-mini")

AGENTS = {
    "real_estate": lambda: RealEstateAgent("the caller"),
    "restaurant": lambda: RestaurantAgent("the caller"),
    "healthcare": lambda: HealthcareAgent("the caller"),
}


GROUNDING_SCHEMA_ADDENDUM = """

RESPONSE FORMAT — STRUCTURAL GROUNDING REQUIREMENT

You must respond with a JSON object matching this exact shape, not plain text:

{
  "spoken_reply": "<what you would actually say to the caller, in character>",
  "claims": [
    {
      "fact": "<the specific fact stated in spoken_reply, e.g. 'warm rent is 1420 euros'>",
      "source_tool_call": "<the exact tool name whose result this fact came from, or null if this claim needs no tool (e.g. a greeting)>"
    }
  ]
}

Rules for "claims":
- List every price, address, date, availability slot, yes/no coverage or
  policy answer, document requirement, or count that appears in
  spoken_reply.
- "source_tool_call" MUST be a tool you actually called earlier in this
  conversation, whose returned data actually contains this fact. Do not name
  a tool you have not called. Do not name a tool whose result does not
  contain this exact fact.
- If a claim has no tool call to support it, you must not make that claim in
  spoken_reply at all. Rewrite spoken_reply to omit it, ask a clarifying
  question instead, or say a colleague will confirm.
- Greetings, acknowledgements, and questions back to the caller need no
  entry in "claims".
"""


class GroundingClaim(BaseModel):
    fact: str
    source_tool_call: str | None


class GroundedReply(BaseModel):
    """Mirrors GROUNDING_SCHEMA_ADDENDUM exactly — this is the actual
    schema handed to the model via response_format, not just prose asking
    for this shape. livekit-agents' inference.LLM only accepts a
    pydantic BaseModel (or TypedDict) for response_format, not a raw
    JSON-schema dict, so this class IS the enforced schema."""
    spoken_reply: str
    claims: list[GroundingClaim]


VERIFICATION_PASS_PROMPT = """You already drafted a reply to the caller in this conversation. Before it is spoken, verify it against the real tool results below.

YOUR DRAFT REPLY:
{draft_reply}

CLAIMS YOU TAGGED:
{draft_claims}

ACTUAL TOOL RESULTS FROM THIS CONVERSATION:
{tool_results}

Check every claim:
- If a claim's "source_tool_call" was never actually called, or the tool's real result does not contain that exact fact, the claim is UNSUPPORTED.
- If any claim is unsupported, rewrite spoken_reply to remove or fix it — do not just remove it from the claims list while leaving the false statement in spoken_reply.
- If everything checks out, you may return the draft unchanged.

Respond with the same JSON shape as before (spoken_reply + claims), containing your FINAL, corrected reply."""


def _format_tool_results_for_verification(tool_calls: list[dict]) -> str:
    if not tool_calls:
        return "(no tools were called)"
    return "\n".join(f"- {tc['tool']}({tc['arguments']}) -> {tc['result']}" for tc in tool_calls)


@dataclass
class ScenarioResult:
    scenario_id: str
    domain: str
    condition: str
    spoken_reply: str
    tool_calls_made: list[dict]
    claims: list[dict] = field(default_factory=list)
    latency_ms: float = 0.0
    grounded: bool | None = None
    task_correct: bool | None = None
    failure_reason: str = ""
    hallucinated_id_attempt: str | None = None
    raw_error: str = ""


def build_tool_defs(agent) -> list:
    return list(agent.tools)


async def call_tool_by_name(agent, tool_name: str, arguments: dict) -> str:
    method = getattr(agent, tool_name, None)
    if method is None:
        return json.dumps({"error": f"no such tool: {tool_name}"})
    try:
        result = await method(ctx=None, **arguments)
        return result if isinstance(result, str) else json.dumps(result)
    except TypeError:
        try:
            result = await method(None, **arguments)
            return result if isinstance(result, str) else json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": str(e)})


async def run_turn(
    agent,
    llm_client: inference.LLM,
    caller_turn: str,
    extra_instructions: str,
    structured: bool,
) -> tuple[str, list[dict], list[dict], float]:
    ctx = ChatContext.empty()
    ctx.add_message(role="system", content=agent.instructions + extra_instructions)
    ctx.add_message(role="user", content=caller_turn)

    tool_calls_made: list[dict] = []
    start = time.perf_counter()

    chat_kwargs: dict[str, object] = {
        "chat_ctx": ctx, "tools": build_tool_defs(agent), "tool_choice": "auto",
    }
    if structured:
        chat_kwargs["response_format"] = GroundedReply

    for _ in range(4):
        stream = llm_client.chat(**chat_kwargs)
        text_parts: list[str] = []
        fn_calls: list = []
        async for chunk in stream:
            if chunk.delta and chunk.delta.content:
                text_parts.append(chunk.delta.content)
            if chunk.delta and chunk.delta.tool_calls:
                fn_calls.extend(chunk.delta.tool_calls)
        await stream.aclose()

        full_text = "".join(text_parts)

        if fn_calls:
            for call in fn_calls:
                args = {}
                try:
                    args = json.loads(call.arguments) if call.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_result = await call_tool_by_name(agent, call.name, args)
                tool_calls_made.append({"tool": call.name, "arguments": args, "result": tool_result})
                ctx.insert(FunctionCall(
                    call_id=call.call_id, name=call.name, arguments=call.arguments or "{}",
                ))
                ctx.insert(FunctionCallOutput(
                    call_id=call.call_id, name=call.name, output=tool_result, is_error=False,
                ))
            continue

        elapsed_ms = (time.perf_counter() - start) * 1000

        if structured:
            try:
                parsed = json.loads(full_text)
                return parsed.get("spoken_reply", full_text), tool_calls_made, parsed.get("claims", []), elapsed_ms
            except json.JSONDecodeError:
                return full_text, tool_calls_made, [], elapsed_ms
        return full_text, tool_calls_made, [], elapsed_ms

    return "[no final reply after 4 tool rounds]", tool_calls_made, [], (time.perf_counter() - start) * 1000


async def run_turn_verified(
    agent,
    llm_client: inference.LLM,
    caller_turn: str,
) -> tuple[str, list[dict], list[dict], float]:
    ctx = ChatContext.empty()
    ctx.add_message(role="system", content=agent.instructions + GROUNDING_SCHEMA_ADDENDUM)
    ctx.add_message(role="user", content=caller_turn)

    tool_calls_made: list[dict] = []
    start = time.perf_counter()
    tools = build_tool_defs(agent)

    draft_reply = ""
    draft_claims: list[dict] = []

    for round_idx in range(4):
        tool_choice = "required" if (round_idx == 0 and tools) else "auto"
        stream = llm_client.chat(
            chat_ctx=ctx, tools=tools, tool_choice=tool_choice,
            response_format=GroundedReply,
        )
        text_parts: list[str] = []
        fn_calls: list = []
        async for chunk in stream:
            if chunk.delta and chunk.delta.content:
                text_parts.append(chunk.delta.content)
            if chunk.delta and chunk.delta.tool_calls:
                fn_calls.extend(chunk.delta.tool_calls)
        await stream.aclose()

        full_text = "".join(text_parts)

        if fn_calls:
            for call in fn_calls:
                args = {}
                try:
                    args = json.loads(call.arguments) if call.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_result = await call_tool_by_name(agent, call.name, args)
                tool_calls_made.append({"tool": call.name, "arguments": args, "result": tool_result})
                ctx.insert(FunctionCall(
                    call_id=call.call_id, name=call.name, arguments=call.arguments or "{}",
                ))
                ctx.insert(FunctionCallOutput(
                    call_id=call.call_id, name=call.name, output=tool_result, is_error=False,
                ))
            continue

        try:
            parsed = json.loads(full_text)
            draft_reply = parsed.get("spoken_reply", full_text)
            draft_claims = parsed.get("claims", [])
        except json.JSONDecodeError:
            draft_reply = full_text
            draft_claims = []
        break
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return "[no final reply after 4 tool rounds]", tool_calls_made, [], elapsed_ms

    verify_ctx = ChatContext.empty()
    verify_ctx.add_message(role="system", content=agent.instructions + GROUNDING_SCHEMA_ADDENDUM)
    verify_ctx.add_message(role="user", content=caller_turn)
    verify_ctx.add_message(role="user", content=VERIFICATION_PASS_PROMPT.format(
        draft_reply=draft_reply,
        draft_claims=json.dumps(draft_claims),
        tool_results=_format_tool_results_for_verification(tool_calls_made),
    ))

    verify_stream = llm_client.chat(
        chat_ctx=verify_ctx, tools=tools, tool_choice="none",
        response_format=GroundedReply,
    )
    verify_text_parts: list[str] = []
    async for chunk in verify_stream:
        if chunk.delta and chunk.delta.content:
            verify_text_parts.append(chunk.delta.content)
    await verify_stream.aclose()

    elapsed_ms = (time.perf_counter() - start) * 1000
    verify_full_text = "".join(verify_text_parts)
    try:
        verified = json.loads(verify_full_text)
        return (
            verified.get("spoken_reply", draft_reply),
            tool_calls_made,
            verified.get("claims", draft_claims),
            elapsed_ms,
        )
    except json.JSONDecodeError:
        return draft_reply, tool_calls_made, draft_claims, elapsed_ms


async def run_domain(set_name: str, domain: str, llm_client: inference.LLM) -> list[ScenarioResult]:
    scenarios = datasets.load_scenarios(set_name, domain)
    results: list[ScenarioResult] = []

    for condition in datasets.CONDITIONS:
        for scenario in scenarios:
            agent = AGENTS[domain]()
            try:
                if condition == "before":
                    reply, tool_calls, claims, ms = await run_turn(
                        agent, llm_client, scenario["caller_turn"], "", False
                    )
                    grounded, reason, hallucinated_id = score_before(scenario, reply, tool_calls)
                elif condition == "after":
                    reply, tool_calls, claims, ms = await run_turn(
                        agent, llm_client, scenario["caller_turn"], GROUNDING_SCHEMA_ADDENDUM, True
                    )
                    grounded, reason, hallucinated_id = score_after(scenario, reply, tool_calls, claims)
                else:
                    reply, tool_calls, claims, ms = await run_turn_verified(
                        agent, llm_client, scenario["caller_turn"]
                    )
                    grounded, reason, hallucinated_id = score_after(scenario, reply, tool_calls, claims)

                results.append(ScenarioResult(
                    scenario_id=scenario["id"], domain=domain, condition=condition,
                    spoken_reply=reply, tool_calls_made=tool_calls, claims=claims,
                    latency_ms=ms, grounded=grounded, failure_reason=reason,
                    hallucinated_id_attempt=hallucinated_id,
                ))
                flag = "  [ID HALLUCINATED]" if hallucinated_id else ""
                print(f"  [{condition:>14}] {scenario['id']}: grounded={grounded} ({reason}) {ms:.0f}ms{flag}")
            except Exception as e:
                results.append(ScenarioResult(
                    scenario_id=scenario["id"], domain=domain, condition=condition,
                    spoken_reply="", tool_calls_made=[], grounded=None,
                    failure_reason="error", raw_error=str(e),
                ))
                print(f"  [{condition:>14}] {scenario['id']}: ERROR {e}")

    return results


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", required=True, choices=datasets.SETS, dest="set_name")
    args = parser.parse_args()

    if not os.environ.get("LIVEKIT_API_KEY"):
        raise SystemExit("LIVEKIT_API_KEY not set. Check .env")

    llm_client = inference.LLM(model=LLM_MODEL)
    all_results: list[ScenarioResult] = []

    for domain in datasets.DOMAINS:
        print(f"\n=== {domain} ===")
        all_results.extend(await run_domain(args.set_name, domain, llm_client))

    out_path = datasets.results_path(args.set_name)
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump([r.__dict__ for r in all_results], f, indent=2)
    print(f"\nWrote {len(all_results)} results to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
