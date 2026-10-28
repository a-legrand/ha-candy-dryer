"""Local protocol of Candy Simply-Fi tumble dryers.

The appliance serves two endpoints on port 80:

- ``/http-read.json?encrypted=1`` returns its status, XOR-encrypted with a
  16-character key and hex-encoded;
- ``/http-write.json?encrypted=1&data=<hex>`` takes a command (a query string),
  encrypted the same way, and answers ``{"response":"SUCCESS"}``.

Command formats come from the Simply-Fi Android app (``CandyTumbleDryerCommand``).
Nothing here does I/O, so it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .programs import Program

KEY_LENGTH = 16

# Known beginnings of the status document, each at least KEY_LENGTH bytes long:
# XOR-ing one of them with the start of the response gives the key.
STATUS_PREFIXES = (
    b'{\r\n\t"statusTD":\r\n{"',
    b'{\r\n\t"statusTD":{\r\n',
    b'{\r\n  "statusTD":{',
    b'{\n\t"statusTD":{\n\t\t',
    b'{"statusTD":{"StatoWiFi":"',
)

# The firmware sometimes emits invalid JSON (e.g. "RecipeId":"NULL \"), so the
# status is read field by field instead of with a JSON parser.
_FIELD = re.compile(r'"(\w+)"\s*:\s*"([^"\\]*)')

MACHINE_STATES = {
    0: "idle",
    1: "idle",
    2: "running",
    3: "paused",
    4: "delay_selection",
    5: "delayed_start",
    6: "test",
    7: "error",
    8: "finished",
}
ACTIVE_STATES = {"running", "paused", "delayed_start"}

PHASES = {0: "stopped", 1: "pre_heating", 2: "drying", 3: "end"}

DRY_LEVELS = {0: "none", 1: "iron", 2: "hang", 3: "store", 4: "bone"}


class InvalidStatusError(ValueError):
    """The response is not a tumble dryer status."""


def xor(data: bytes, key: bytes) -> bytes:
    """Apply the repeating XOR key (an empty key leaves data unchanged)."""
    if not key:
        return data
    return bytes(byte ^ key[i % len(key)] for i, byte in enumerate(data))


def encrypt_command(query: str, key: str) -> str:
    """Encrypt a command for the ``data`` parameter of http-write.json."""
    return xor(query.encode(), key.encode()).hex().upper()


def decrypt_response(text: str, key: str) -> str:
    """Decrypt a hex-encoded response."""
    return xor(bytes.fromhex(text.strip()), key.encode()).decode("latin-1")


def parse_fields(text: str) -> dict[str, str]:
    """Extract the "Name":"value" pairs of a status document."""
    return {name: value.strip() for name, value in _FIELD.findall(text)}


def find_key(response_hex: str) -> str:
    """Recover the key from an encrypted status response.

    Returns "" when the response is hex-encoded but not encrypted, which some
    firmwares do. Raises InvalidStatusError when no known layout matches.
    """
    data = bytes.fromhex(response_hex.strip())
    if b"StatoTD" in data:
        return ""
    for prefix in STATUS_PREFIXES:
        key = xor(data[:KEY_LENGTH], prefix[:KEY_LENGTH])
        if not all(0x20 <= byte < 0x7F for byte in key):
            continue
        if "StatoTD" in parse_fields(xor(data, key).decode("latin-1")):
            return key.decode()
    raise InvalidStatusError("Could not recover the encryption key")


@dataclass(frozen=True)
class DryerStatus:
    """Status reported by the dryer."""

    machine_state: str | None
    phase: str | None
    program: int
    remaining_minutes: int
    dry_level: str | None
    remote_control: bool
    door_closed: bool
    clean_filter: bool
    water_tank_full: bool
    error_code: int

    @property
    def is_active(self) -> bool:
        """A cycle is running, paused or waiting for its delayed start."""
        return self.machine_state in ACTIVE_STATES

    @classmethod
    def from_text(cls, text: str) -> DryerStatus:
        """Build the status from a decrypted status document."""
        fields = parse_fields(text)
        if "StatoTD" not in fields:
            raise InvalidStatusError("Not a tumble dryer status")

        def number(name: str) -> int:
            try:
                return int(fields.get(name, "0"))
            except ValueError:
                return 0

        return cls(
            machine_state=MACHINE_STATES.get(number("StatoTD")),
            phase=PHASES.get(number("PrPh")),
            program=number("Pr"),
            remaining_minutes=number("RemTime"),
            dry_level=DRY_LEVELS.get(number("DryLev")),
            remote_control=fields.get("StatoWiFi") == "1",
            door_closed=fields.get("DoorState") == "1",
            clean_filter=fields.get("CleanFilter") == "1",
            water_tank_full=fields.get("WaterTankFull") == "1",
            error_code=number("CodiceErrore"),
        )


def start_command(
    program: Program, time_level: int | None = None, delay_minutes: int = 0
) -> str:
    """Start a program, as the Simply-Fi app does for Rapid'O dryers.

    time_level is the duration chosen for a timed program: Time switches the
    dryer from its humidity sensor to a fixed duration. Extra programs add
    their fixed settings. A delayed start waits delay_minutes.
    """
    query = f"Write=1&Pa=0&Sel=0&PrNm={program.position}&StSt=1"
    level = time_level or program.time_level
    if level:
        query += f"&Time={level}"
    if program.dry_level:
        query += f"&DryLev={program.dry_level}"
    if delay_minutes:
        query += f"&DelMd=1&DelVl={delay_minutes}"
    return query + "&RecipeId=NULL"


def stop_command(program: int) -> str:
    """Stop the running cycle."""
    return f"Write=1&StSt=0&DelMd=0&PrNm={program}"


# Pause and resume a running cycle, as the play/pause button of the app does
# for Rapid'O dryers (tdlibrary APIAccessor.pauseDryManager/resumeDryManager).
PAUSE_COMMAND = "Write=1&SetPauseDryMgr=1"
RESUME_COMMAND = "Write=1&SetRestartDryMgr=1"
