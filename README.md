# Grounded voice agent

This is the code and data behind the thesis *Checking Before Speaking*, which asks how to stop a voice agent from stating business facts it never looked up. It has two parts:

- **The live app:** an outbound phone agent built on LiveKit Agents and a Twilio SIP trunk. It serves several personas, and each persona can state business facts only by calling a tool.
- **The experiment:** it gives the same questions to three versions of the agent (P1 prompt only, P2 cited schema, P3 forced tool call plus self-verification) and scores every answer for groundedness. The analysis scripts then produce every number and chart in the thesis.

## Structure

```
app/              live phone calls
  worker.py         LiveKit agent worker, one process for every persona
  dashboard.py      web dashboard backend (dashboard.html is the page)
  dial.py           place a call from the terminal
  dispatch.py       the one function that dispatches a call
  provision.py      one-time Twilio + LiveKit trunk setup
personas/         who the model speaks as
  registry.py       personas available on live calls
  prompts.py        prompt blocks shared by all personas
  real_estate.py    Anna, Berlin Home Rentals (16 tools)
  restaurant.py     Lena, Zur Goldenen Gans (16 tools)
  healthcare.py     Petra, Riverside Practice (11 tools, experiment only)
knowledge_base/   the only source of business facts, one module per persona
experiment/       generate and score the answers
  run.py            runs the three conditions over a question set
  scorer.py         the deterministic groundedness check
  rescore.py        re-scores stored answers without calling the model
  review_sheet.py   builds the H1/H2 human review sheet
  datasets.py       paths for the golden and hard sets
  SCORER_NOTES.md   why each scoring rule exists
  scenarios/        golden (90 questions) and hard (120 questions)
  results/          stored answers and review sheets for each set
analysis/         every number and chart in the thesis
  settings.py       every fixed value: condition names, statistical constants, colours, figure sizes
  formulas.py       the statistical formulas (Wilson, McNemar, Holm, kappa, ...)
  audit_codes.csv   the hand-audit verdicts, one row per coded answer
  stats.py          rates, paired tests, latency, agreement
  audit.py          transcript audit and sensitivity analyses
  charts.py         the charts and diagrams in thesis/figures
  output/           stats.json, audit_stats.json, audit_transcripts.csv
thesis/figures/   the charts and diagrams charts.py produces for the thesis
```

The same key names each domain everywhere: `real_estate`, `restaurant` and `healthcare`. It is used for the persona, its knowledge base, its scenario file and its registry entry.

## Setup

```bash
uv sync
```

Create a `.env` file in the project root. The live app and the experiment both need `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`. Phone calls also need the Twilio values, and `provision.py` writes those for you:

| Variable | Used by | Meaning |
|---|---|---|
| `TWILIO_SID`, `TWILIO_CLIENT_SECRET`, `TWILIO_ACCOUNT_SID` | provision | Twilio API key and account |
| `TWILIO_SIP_TERMINATION_URI`, `TWILIO_SIP_USERNAME`, `TWILIO_SIP_PASSWORD`, `TWILIO_PHONE_NUMBER` | provision, written by it | Twilio SIP trunk and caller ID |
| `SIP_OUTBOUND_TRUNK_ID` | worker, dial, dashboard | LiveKit outbound trunk, written by provision |
| `LLM_MODEL`, `STT_MODEL`, `TTS_MODEL`, `TTS_VOICE`, `TTS_FALLBACKS` | worker (`LLM_MODEL` also experiment) | model choice, all through LiveKit Inference |
| `AMD_MODEL`, `LEAVE_VOICEMAIL`, `DEFAULT_COUNTRY_CODE` | worker, dashboard | answering-machine detection and number format |

## Running the live app

All commands run from the project root.

```bash
uv run python -m app.provision                  # once: Twilio number, SIP trunk, LiveKit trunk (paid Twilio account)
uv run python -m app.provision --livekit-only   # only rebuild the LiveKit trunk from the values in .env

uv run python -m app.worker dev                 # terminal 1: the agent worker
uv run python -m app.dashboard                  # terminal 2: open http://localhost:8080
uv run python -m app.dial +4915112345678 restaurant "Name"
uv run python -m app.worker console             # talk to the agent through your laptop microphone, no phone costs
```

LiveKit 1.6 prints a notice that `dev` is deprecated in favour of `lk agent dev`. Both work, and `lk agent dev` adds hot reload.

Default models are `deepgram/nova-3` for speech to text, `openai/gpt-4.1-mini` for the language model and `cartesia/sonic-3.5` for text to speech, with `cartesia/sonic-2` and `inworld/inworld-tts-1.5` as fallbacks. The dashboard can dial Germany, Austria, Switzerland, the UK, the US and Canada, and India. To add a country, add its prefix to `ALLOWED_PREFIXES` in `app/dashboard.py` and enable it in Twilio Voice geo permissions.

To add a persona, write an `Agent` subclass with `@function_tool` methods in `personas/` and its data in `knowledge_base/`, then register it in `personas/registry.py`. The dashboard picks it up automatically.

## Reproducing the thesis

Only the first command calls the model. Everything after it reads the stored answers in `experiment/results/`. The thesis answers were generated with `LLM_MODEL=openai/gpt-4.1` in `.env`. Without that line the code falls back to `openai/gpt-4.1-mini`, which would give different answers.

```bash
uv run python -m experiment.run --set hard            # or --set golden; overwrites that set's results
uv run python -m experiment.rescore --set hard        # re-score stored answers
uv run python -m experiment.review_sheet --set hard   # rebuild the review sheet, keeping H1/H2 verdicts
uv run python -m analysis.stats                       # -> analysis/output/stats.json
uv run python -m analysis.audit                       # -> analysis/output/audit_stats.json, audit_transcripts.csv
uv run --group analysis python -m analysis.charts     # -> thesis/figures
```

The thesis document itself is not part of this repository. If the data changes, re-run the charts and replace the images in the thesis by hand.

Where each thesis result comes from:

| Result | Script | Key in the output |
|---|---|---|
| Grounded-answer rates, Wilson intervals | `analysis/stats.py` | `rates`, `by_domain`, `by_difficulty` |
| Exact McNemar with Holm adjustment, power floor, fix and break rates | `analysis/stats.py` | `pairwise`, `power_floor_80pct`, `p3_vs_p1_fix_break` |
| Latency (medians, questions where P2 or P3 was slower than P1) | `analysis/stats.py` | `latency`, `latency_tests` |
| H1/H2 agreement (kappa, PABAK) | `analysis/stats.py` | `sheet` |
| Lookups skipped, tool use, claims | `analysis/stats.py` | `tool_use`, `claims` |
| Safety questions (112 and clinical refusals) | `analysis/stats.py` | `safety`, `safety_pooled` |
| Scorer accuracy against the audit, trap accuracy | `analysis/audit.py` | `scorer_vs_audit_trap`, `trap_audit` |
| Sensitivity analyses | `analysis/audit.py` | `hard_sensitivity`, `hard_two_sided` |

The audit verdicts in `analysis/audit_codes.csv` were assigned by reading each transcript. If you disagree with one, edit its row (a spreadsheet works) and re-run `analysis.audit`. The script checks that every answer the scorer failed has a verdict, and stops if one is missing. Counts shown in the figures, such as the number of questions and answers, are calculated from the results rather than typed in.

## Known limitations

- The healthcare prompt mentions a `reschedule_appointment` tool that the healthcare agent does not have. It is left in place because changing the prompt would change the experiment.
- Tool docstrings are part of the prompt: LiveKit sends them to the model as tool descriptions. The `GroundedReply` docstring in `experiment/run.py` is sent as the P2/P3 schema description. Editing any of them changes what the model sees.
- `app/worker.py` sets the text-to-speech language to `de`, although the personas speak English only.
- Running `provision.py` again writes a new random SIP password into `.env` even when the Twilio credential already exists. Calls keep working, because the LiveKit trunk holds the real password.

## Legal note

In Germany and Austria, unsolicited commercial calls to consumers need prior consent (UWG §7 in Germany, TKG §174 in Austria), and GDPR applies on top. Demo calls to yourself and to colleagues who expect the call are fine. Building a cold-call list from this is not.
