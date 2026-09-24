from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import string
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from livekit import api

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

AUTH = (os.environ.get("TWILIO_SID", ""), os.environ.get("TWILIO_CLIENT_SECRET", ""))
API = f"https://api.twilio.com/2010-04-01/Accounts/{os.environ.get('TWILIO_ACCOUNT_SID', '')}"
TRUNKING = "https://trunking.twilio.com/v1"
VOICE = "https://voice.twilio.com/v1"

TRUNK_FRIENDLY_NAME = "livekit-agent"
CRED_LIST_NAME = "livekit-agent-creds"
LIVEKIT_TRUNK_NAME = "twilio-outbound"
DIAL_COUNTRY = "DE"


def require(var: str) -> str:
    value = os.environ.get(var, "").strip()
    if not value:
        sys.exit(f"Missing {var} in .env. See README.md.")
    return value


def call(method: str, url: str, **kw) -> dict:
    r = requests.request(method, url, auth=AUTH, timeout=30, **kw)
    if r.status_code == 401 and r.json().get("code") == 20003:
        sys.exit(
            "\nTwilio says this feature needs a paid account (error 20003).\n"
            "Upgrade at https://console.twilio.com/billing, then re-run this script.\n"
        )
    if not r.ok:
        sys.exit(f"\nTwilio API error on {method} {url}\n  {r.status_code}: {r.text[:400]}\n")
    return r.json() if r.text else {}


def strong_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(20))
        if any(c.isupper() for c in pw) and any(c.islower() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def write_env(updates: dict[str, str]) -> None:
    text = ENV_PATH.read_text()
    for key, value in updates.items():
        line = f"{key}={value}"
        if re.search(rf"^{re.escape(key)}=.*$", text, flags=re.M):
            text = re.sub(rf"^{re.escape(key)}=.*$", line, text, flags=re.M)
        else:
            text = text.rstrip("\n") + f"\n{line}\n"
    ENV_PATH.write_text(text)


def buy_number() -> tuple[str, str]:
    owned = call("GET", f"{API}/IncomingPhoneNumbers.json").get("incoming_phone_numbers", [])
    if owned:
        n = owned[0]
        print(f"  using existing number {n['phone_number']}")
        return n["phone_number"], n["sid"]

    available = call(
        "GET", f"{API}/AvailablePhoneNumbers/US/Local.json", params={"VoiceEnabled": "true", "PageSize": 1}
    ).get("available_phone_numbers", [])
    if not available:
        sys.exit("No US local numbers available to purchase.")

    number = available[0]["phone_number"]
    bought = call("POST", f"{API}/IncomingPhoneNumbers.json", data={"PhoneNumber": number})
    print(f"  bought {bought['phone_number']}  (~$1.15/month)")
    return bought["phone_number"], bought["sid"]


def make_credential_list(username: str, password: str) -> str:
    for cl in call("GET", f"{API}/SIP/CredentialLists.json").get("credential_lists", []):
        if cl["friendly_name"] == CRED_LIST_NAME:
            print("  credential list already exists")
            return cl["sid"]

    cl = call("POST", f"{API}/SIP/CredentialLists.json", data={"FriendlyName": CRED_LIST_NAME})
    call(
        "POST",
        f"{API}/SIP/CredentialLists/{cl['sid']}/Credentials.json",
        data={"Username": username, "Password": password},
    )
    print(f"  created credential list, username '{username}'")
    return cl["sid"]


def make_trunk(domain_name: str, cred_list_sid: str, number_sid: str) -> str:
    for t in call("GET", f"{TRUNKING}/Trunks").get("trunks", []):
        if t["friendly_name"] == TRUNK_FRIENDLY_NAME:
            print(f"  trunk already exists: {t['domain_name']}")
            return t["domain_name"]

    trunk = call(
        "POST",
        f"{TRUNKING}/Trunks",
        data={"FriendlyName": TRUNK_FRIENDLY_NAME, "DomainName": domain_name},
    )
    sid = trunk["sid"]
    call("POST", f"{TRUNKING}/Trunks/{sid}/CredentialLists", data={"CredentialListSid": cred_list_sid})
    call("POST", f"{TRUNKING}/Trunks/{sid}/PhoneNumbers", data={"PhoneNumberSid": number_sid})
    print(f"  created trunk {trunk['domain_name']}")
    return trunk["domain_name"]


def enable_country(iso: str) -> None:
    payload = [{"iso_code": iso, "low_risk_numbers_enabled": True,
                "high_risk_special_numbers_enabled": False,
                "high_risk_tollfraud_numbers_enabled": False}]
    r = requests.post(
        f"{VOICE}/DialingPermissions/BulkCountryUpdates",
        auth=AUTH, timeout=30, data={"UpdateRequest": json.dumps(payload)},
    )
    print(f"  geo permission for {iso}: {'enabled' if r.ok else 'check console manually'}")


async def make_livekit_trunk(address: str, number: str, username: str, password: str) -> str:
    lk = api.LiveKitAPI()
    try:
        for t in (await lk.sip.list_sip_outbound_trunk(api.ListSIPOutboundTrunkRequest())).items:
            if t.name == LIVEKIT_TRUNK_NAME:
                print("  LiveKit trunk already exists")
                return t.sip_trunk_id

        created = await lk.sip.create_sip_outbound_trunk(
            api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(
                    name=LIVEKIT_TRUNK_NAME,
                    address=address,
                    numbers=[number],
                    auth_username=username,
                    auth_password=password,
                )
            )
        )
        print(f"  created LiveKit trunk {created.sip_trunk_id}")
        return created.sip_trunk_id
    finally:
        await lk.aclose()


async def provision_livekit_only() -> None:
    address = require("TWILIO_SIP_TERMINATION_URI").removeprefix("sip:")
    username = require("TWILIO_SIP_USERNAME")
    password = require("TWILIO_SIP_PASSWORD")
    number = require("TWILIO_PHONE_NUMBER")

    print("LiveKit:")
    trunk_id = await make_livekit_trunk(address, number, username, password)
    write_env({"SIP_OUTBOUND_TRUNK_ID": trunk_id})
    print(f"\nDone. .env updated.\n\nSIP_OUTBOUND_TRUNK_ID={trunk_id}\n")


async def provision_all() -> None:
    for var in ("TWILIO_SID", "TWILIO_CLIENT_SECRET", "TWILIO_ACCOUNT_SID"):
        require(var)

    acct = call("GET", f"{API}.json")
    print(f"Twilio account: {acct['friendly_name']} ({acct['type']})\n")
    if acct["type"] == "Trial":
        sys.exit(
            "This is a Trial account. Elastic SIP Trunking is not available on Trial.\n"
            "Upgrade at https://console.twilio.com/billing (~$20 minimum), then re-run.\n"
        )

    username = "lkagent"
    password = strong_password()
    domain = f"lk-{secrets.token_hex(4)}.pstn.twilio.com"

    print("Twilio:")
    number, number_sid = buy_number()
    cred_list_sid = make_credential_list(username, password)
    domain = make_trunk(domain, cred_list_sid, number_sid)
    enable_country(DIAL_COUNTRY)

    print("\nLiveKit:")
    trunk_id = await make_livekit_trunk(domain, number, username, password)

    write_env(
        {
            "TWILIO_SIP_TERMINATION_URI": domain,
            "TWILIO_SIP_USERNAME": username,
            "TWILIO_SIP_PASSWORD": password,
            "TWILIO_PHONE_NUMBER": number,
            "SIP_OUTBOUND_TRUNK_ID": trunk_id,
        }
    )

    print(
        "\nDone. .env updated.\n\nNow run:\n"
        "  uv run python -m app.worker dev\n"
        "  uv run python -m app.dial +49XXXXXXXXXX real_estate \"Name\"\n"
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--livekit-only", action="store_true")
    args = parser.parse_args()
    if args.livekit_only:
        await provision_livekit_only()
    else:
        await provision_all()


if __name__ == "__main__":
    asyncio.run(main())
