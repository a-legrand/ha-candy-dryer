"""Fixtures for the Candy dryer tests."""

from __future__ import annotations

import pytest

from custom_components.candy_dryer.protocol import xor

KEY = "Q7xK2mPz9LwR4tVb"


def status_document(**fields: str) -> str:
    """A status in the layout of a real dryer, with some fields overridden."""
    values = {
        "StatoWiFi": "1",
        "StatoTD": "1",
        "CodiceErrore": "0",
        "Pr": "15",
        "PrPh": "0",
        "RemTime": "150",
        "DryLev": "2",
        "CleanFilter": "0",
        "WaterTankFull": "0",
        "DoorState": "1",
        "RecipeId": "NULL",
        **fields,
    }
    body = ",\r\n\t\t".join(f'"{name}":"{value}"' for name, value in values.items())
    return '{\r\n\t"statusTD":\r\n{' + body + "\r\n\t}\r\n}"


def encrypt(text: str, key: str = KEY) -> str:
    """Hex-encoded encrypted response, as the dryer sends it."""
    return xor(text.encode(), key.encode()).hex().upper()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components/."""
