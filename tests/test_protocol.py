"""Tests of the dryer protocol."""

from __future__ import annotations

import pytest

from custom_components.candy_dryer.programs import PROGRAMS_BY_KEY
from custom_components.candy_dryer.protocol import (
    DryerStatus,
    InvalidStatusError,
    decrypt_response,
    encrypt_command,
    find_key,
    start_command,
    stop_command,
)

from .conftest import KEY, encrypt, status_document


def test_find_key_from_encrypted_status() -> None:
    assert find_key(encrypt(status_document())) == KEY


def test_find_key_from_unencrypted_hex_status() -> None:
    assert find_key(status_document().encode().hex()) == ""


def test_find_key_rejects_other_documents() -> None:
    with pytest.raises(InvalidStatusError):
        find_key(encrypt('{"response":"BAD REQUEST"}' * 2))


def test_status_decoding() -> None:
    status = DryerStatus.from_text(decrypt_response(encrypt(status_document()), KEY))
    assert status == DryerStatus(
        machine_state="idle",
        phase="stopped",
        program=15,
        remaining_minutes=150,
        dry_level="hang",
        remote_control=True,
        door_closed=True,
        clean_filter=False,
        water_tank_full=False,
        error_code=0,
    )
    assert not status.is_active


def test_status_tolerates_invalid_json_from_firmware() -> None:
    # Seen on a real dryer during a cycle started with RecipeId=NULL.
    text = status_document(StatoTD="2", PrPh="2").replace('"NULL"', '"NULL \\"')
    status = DryerStatus.from_text(text)
    assert status.machine_state == "running"
    assert status.phase == "drying"
    assert status.is_active


def test_status_rejects_other_documents() -> None:
    with pytest.raises(InvalidStatusError):
        DryerStatus.from_text('{"response":"SUCCESS"}')


def test_start_commands() -> None:
    # Without a duration, the humidity sensor ends the cycle: no Time.
    assert start_command(PROGRAMS_BY_KEY["whites"]) == (
        "Write=1&Pa=0&Sel=0&PrNm=13&StSt=1&RecipeId=NULL"
    )
    assert start_command(PROGRAMS_BY_KEY["relax_creases"]) == (
        "Write=1&Pa=0&Sel=0&PrNm=6&StSt=1&RecipeId=NULL"
    )


def test_start_commands_with_duration() -> None:
    # Tried on the real dryer: Whites for 90 min.
    assert start_command(PROGRAMS_BY_KEY["whites"], time_level=7) == (
        "Write=1&Pa=0&Sel=0&PrNm=13&StSt=1&Time=7&RecipeId=NULL"
    )
    assert start_command(PROGRAMS_BY_KEY["whites"], time_level=9) == (
        "Write=1&Pa=0&Sel=0&PrNm=13&StSt=1&Time=9&RecipeId=NULL"
    )


def test_start_commands_with_dry_level() -> None:
    assert start_command(PROGRAMS_BY_KEY["eco_cotton"], dry_level=4) == (
        "Write=1&Pa=0&Sel=0&PrNm=14&StSt=1&DryLev=4&RecipeId=NULL"
    )


def test_delayed_start() -> None:
    assert start_command(PROGRAMS_BY_KEY["eco_cotton"], delay_minutes=180) == (
        "Write=1&Pa=0&Sel=0&PrNm=14&StSt=1&DelMd=1&DelVl=180&RecipeId=NULL"
    )


def test_start_extra_programs() -> None:
    assert start_command(PROGRAMS_BY_KEY["extra_bed_linen"]) == (
        "Write=1&Pa=0&Sel=0&PrNm=13&StSt=1&DryLev=4&RecipeId=NULL"
    )
    assert start_command(PROGRAMS_BY_KEY["extra_backpacks"]) == (
        "Write=1&Pa=0&Sel=0&PrNm=10&StSt=1&Time=7&RecipeId=NULL"
    )
    assert start_command(PROGRAMS_BY_KEY["extra_air_refresh"]) == (
        "Write=1&Pa=0&Sel=0&PrNm=3&StSt=1&RecipeId=NULL"
    )


def test_stop_command() -> None:
    assert stop_command(15) == "Write=1&StSt=0&DelMd=0&PrNm=15"


def test_command_encryption_round_trip() -> None:
    hex_data = encrypt_command(stop_command(15), KEY)
    assert hex_data == hex_data.upper()
    assert decrypt_response(hex_data, KEY) == stop_command(15)
