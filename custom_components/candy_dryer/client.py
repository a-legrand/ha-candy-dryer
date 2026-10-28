"""HTTP client for the dryer's local API."""

from __future__ import annotations

import asyncio

import aiohttp

from .protocol import (
    DryerStatus,
    InvalidStatusError,
    decrypt_response,
    encrypt_command,
    find_key,
)

# Short enough that polling a switched-off dryer stays cheap.
REQUEST_TIMEOUT = 5


class CandyError(Exception):
    """Base error of the client."""


class CandyConnectionError(CandyError):
    """The dryer does not answer, usually because it is switched off."""


class CandyCommandError(CandyError):
    """The dryer refused a command."""


async def _get(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT), session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()
    except (TimeoutError, aiohttp.ClientError, OSError) as err:
        raise CandyConnectionError(f"{url}: {err!r}") from err


async def discover_key(session: aiohttp.ClientSession, host: str) -> str:
    """Read the dryer once and recover its encryption key."""
    text = await _get(session, f"http://{host}/http-read.json?encrypted=1")
    try:
        return find_key(text)
    except ValueError as err:
        raise InvalidStatusError(str(err)) from err


class CandyDryerClient:
    """Reads the status of one dryer and sends it commands."""

    def __init__(self, session: aiohttp.ClientSession, host: str, key: str) -> None:
        self._session = session
        self._host = host
        self._key = key
        # The appliance handles one request at a time.
        self._lock = asyncio.Lock()

    async def read_status(self) -> DryerStatus:
        """Fetch and decode the current status."""
        async with self._lock:
            text = await _get(
                self._session, f"http://{self._host}/http-read.json?encrypted=1"
            )
        try:
            return DryerStatus.from_text(decrypt_response(text, self._key))
        except ValueError as err:
            raise InvalidStatusError(str(err)) from err

    async def send(self, query: str) -> None:
        """Send a command and check that the dryer accepted it."""
        data = encrypt_command(query, self._key)
        async with self._lock:
            text = await _get(
                self._session,
                f"http://{self._host}/http-write.json?encrypted=1&data={data}",
            )
        try:
            answer = decrypt_response(text, self._key)
        except ValueError:
            answer = text
        if "SUCCESS" not in answer:
            raise CandyCommandError(f"Command {query!r} refused: {answer[:100]!r}")
