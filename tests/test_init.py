"""Tests of the entities and of the polling of a dryer that is often off."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.candy_dryer.const import (
    ACTIVE_INTERVAL,
    CONF_KEY,
    DOMAIN,
    IDLE_INTERVAL,
    OFF_INTERVAL,
)
from custom_components.candy_dryer.protocol import decrypt_response
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError

from .conftest import KEY, encrypt, status_document

READ_URL = "http://192.0.2.10/http-read.json?encrypted=1"
WRITE_URL = "http://192.0.2.10/http-write.json"


async def setup_dryer(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Candy dryer",
        data={CONF_HOST: "192.0.2.10", CONF_KEY: KEY},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def answer(aioclient_mock: AiohttpClientMocker, **fields: str) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(READ_URL, text=encrypt(status_document(**fields)))


def switch_off(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(READ_URL, exc=TimeoutError())


async def choose(hass: HomeAssistant, program: str) -> None:
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.candy_dryer_program_to_start", ATTR_OPTION: program},
        blocking=True,
    )


async def poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory, delay) -> None:
    freezer.tick(delay)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_idle_dryer(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    answer(aioclient_mock)
    entry = await setup_dryer(hass)

    assert hass.states.get("sensor.candy_dryer_state").state == "idle"
    # Dial on its remote control position.
    assert hass.states.get("sensor.candy_dryer_program").state == "remote"
    assert hass.states.get("sensor.candy_dryer_remaining_time").state == "150"
    assert hass.states.get("sensor.candy_dryer_dry_level").state == "hang"
    assert hass.states.get("sensor.candy_dryer_end_time").state == "unknown"
    assert hass.states.get("binary_sensor.candy_dryer_door").state == "off"
    assert hass.states.get("button.candy_dryer_stop").state == STATE_UNAVAILABLE
    assert entry.runtime_data.update_interval == IDLE_INTERVAL

    # ECO Cotton is the program to start until another one is chosen.
    assert hass.states.get("select.candy_dryer_program_to_start").state == "eco_cotton"
    assert hass.states.get("button.candy_dryer_start_pause").state != STATE_UNAVAILABLE


async def test_switched_off_at_startup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    switch_off(aioclient_mock)
    entry = await setup_dryer(hass)

    assert hass.states.get("sensor.candy_dryer_state").state == "off"
    assert (
        hass.states.get("sensor.candy_dryer_remaining_time").state == STATE_UNAVAILABLE
    )
    assert hass.states.get("button.candy_dryer_start_pause").state == STATE_UNAVAILABLE
    assert entry.runtime_data.update_interval == OFF_INTERVAL


async def test_switching_off_and_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    answer(aioclient_mock)
    entry = await setup_dryer(hass)

    switch_off(aioclient_mock)
    await poll(hass, freezer, IDLE_INTERVAL)
    assert hass.states.get("sensor.candy_dryer_state").state == "off"
    assert entry.runtime_data.update_interval == OFF_INTERVAL

    answer(aioclient_mock)
    await poll(hass, freezer, OFF_INTERVAL)
    assert hass.states.get("sensor.candy_dryer_state").state == "idle"
    assert entry.runtime_data.update_interval == IDLE_INTERVAL


async def test_missed_polls_during_a_cycle(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    answer(aioclient_mock, StatoTD="2", PrPh="2", RemTime="90")
    entry = await setup_dryer(hass)
    assert hass.states.get("sensor.candy_dryer_state").state == "running"
    assert hass.states.get("sensor.candy_dryer_end_time").state != "unknown"
    assert entry.runtime_data.update_interval == ACTIVE_INTERVAL

    switch_off(aioclient_mock)
    await poll(hass, freezer, ACTIVE_INTERVAL)
    await poll(hass, freezer, ACTIVE_INTERVAL)
    assert hass.states.get("sensor.candy_dryer_state").state == "running"

    await poll(hass, freezer, ACTIVE_INTERVAL)
    assert hass.states.get("sensor.candy_dryer_state").state == "off"


async def test_start_button(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    answer(aioclient_mock)
    entry = await setup_dryer(hass)
    await choose(hass, "whites")
    # Right after the command, the real dryer still reports itself idle.
    answer(aioclient_mock, Pr="13")
    aioclient_mock.get(WRITE_URL, text=encrypt('{"response":"SUCCESS"}'))

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.candy_dryer_start_pause"},
        blocking=True,
    )
    await hass.async_block_till_done()

    writes = [
        call for call in aioclient_mock.mock_calls if call[1].path == "/http-write.json"
    ]
    assert len(writes) == 1
    assert decrypt_response(writes[0][1].query["data"], KEY) == (
        "Write=1&Pa=0&Sel=0&PrNm=13&StSt=1&RecipeId=NULL"
    )
    assert hass.states.get("sensor.candy_dryer_state").state == "idle"
    assert entry.runtime_data.update_interval == ACTIVE_INTERVAL

    answer(aioclient_mock, Pr="13", StatoTD="2", PrPh="2")
    await poll(hass, freezer, ACTIVE_INTERVAL)
    assert hass.states.get("sensor.candy_dryer_state").state == "running"
    assert hass.states.get("sensor.candy_dryer_program").state == "whites"


async def test_refused_command(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    answer(aioclient_mock)
    await setup_dryer(hass)
    await choose(hass, "whites")
    aioclient_mock.get(WRITE_URL, text=encrypt('{"response":"BAD REQUEST"}'))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.candy_dryer_start_pause"},
            blocking=True,
        )


async def test_buttons_need_remote_control(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    answer(aioclient_mock, StatoWiFi="0")
    await setup_dryer(hass)
    await choose(hass, "whites")
    assert hass.states.get("button.candy_dryer_start_pause").state == STATE_UNAVAILABLE


async def test_program_choice_survives_restart(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_restore_cache(hass, [State("select.candy_dryer_program_to_start", "jeans")])
    switch_off(aioclient_mock)
    entry = await setup_dryer(hass)

    # The choice is kept, and can be made while the dryer is off.
    assert hass.states.get("select.candy_dryer_program_to_start").state == "jeans"
    assert entry.runtime_data.selected_program.position == 12


async def test_duration_choice(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    answer(aioclient_mock)
    await setup_dryer(hass)
    duration = "select.candy_dryer_program_to_start_duration"

    await choose(hass, "eco_cotton")
    assert hass.states.get(duration).attributes["options"] == ["default"]

    await choose(hass, "synthetics")
    assert hass.states.get(duration).attributes["options"] == [
        "default",
        *(f"min_{minutes}" for minutes in range(70, 160, 10)),
    ]
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: duration, ATTR_OPTION: "min_90"},
        blocking=True,
    )
    assert hass.states.get(duration).state == "min_90"

    aioclient_mock.get(WRITE_URL, text=encrypt('{"response":"SUCCESS"}'))
    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.candy_dryer_start_pause"},
        blocking=True,
    )
    writes = [
        call for call in aioclient_mock.mock_calls if call[1].path == "/http-write.json"
    ]
    assert decrypt_response(writes[0][1].query["data"], KEY) == (
        "Write=1&Pa=0&Sel=0&PrNm=10&StSt=1&Time=7&RecipeId=NULL"
    )

    # A program without durations drops the choice.
    await choose(hass, "extra_bed_linen")
    assert hass.states.get(duration).state == "default"


@pytest.mark.parametrize(
    ("state", "command"),
    [("2", "Write=1&SetPauseDryMgr=1"), ("3", "Write=1&SetRestartDryMgr=1")],
)
async def test_play_pause_during_a_cycle(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    state: str,
    command: str,
) -> None:
    answer(aioclient_mock, StatoTD=state, PrPh="2")
    await setup_dryer(hass)
    assert hass.states.get("button.candy_dryer_stop").state != STATE_UNAVAILABLE
    aioclient_mock.get(WRITE_URL, text=encrypt('{"response":"SUCCESS"}'))

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.candy_dryer_start_pause"},
        blocking=True,
    )

    writes = [
        call for call in aioclient_mock.mock_calls if call[1].path == "/http-write.json"
    ]
    assert decrypt_response(writes[0][1].query["data"], KEY) == command


async def test_delayed_start(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    answer(aioclient_mock)
    await setup_dryer(hass)
    delay = "select.candy_dryer_program_to_start_delayed_start"
    assert hass.states.get(delay).state == "now"
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: delay, ATTR_OPTION: "h_3"},
        blocking=True,
    )
    aioclient_mock.get(WRITE_URL, text=encrypt('{"response":"SUCCESS"}'))

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.candy_dryer_start_pause"},
        blocking=True,
    )
    await hass.async_block_till_done()

    writes = [
        call for call in aioclient_mock.mock_calls if call[1].path == "/http-write.json"
    ]
    assert decrypt_response(writes[0][1].query["data"], KEY) == (
        "Write=1&Pa=0&Sel=0&PrNm=14&StSt=1&DelMd=1&DelVl=180&RecipeId=NULL"
    )
    # The next start is immediate again.
    assert hass.states.get(delay).state == "now"
