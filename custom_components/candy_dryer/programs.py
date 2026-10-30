"""Programs of the Candy RO H9A2TE-S (interface TD_RAPIDO_5D_HP_DOOR).

Standard programs were fetched once from the Simply-Fi cloud (appliances.json):
each is a position of the dial. Position 15 is listed as "Whites" like
position 13: it is the remote control position of the dial, which runs Whites
by default.

Extra programs come from the cloud catalog (td_wifi_download_programs.json),
converted the way the Simply-Fi app does for this dryer (tdlibrary
DryerProgram.SearchProgramDownload): each runs a standard program with fixed
settings. Those running ECO 30' with a 30 min Rapido are plain ECO 30' here,
as the dryer ignores Rapido.
"""

from __future__ import annotations

from dataclasses import dataclass

# Duration of each time level, sent as Time. The app also offers 30, 45 and
# 59 min (Rapido, or Time 1-3), which this dryer ignores.
TIME_LEVEL_MINUTES = {level: 70 + 10 * (level - 5) for level in range(5, 21)}


def _time_levels(max_level: int) -> tuple[int, ...]:
    return tuple(range(5, max_level + 1))


@dataclass(frozen=True)
class Program:
    """A program and what the Simply-Fi app sends with it."""

    key: str
    position: int
    # Durations that can be chosen ("timed" programs of the app).
    time_levels: tuple[int, ...] = ()
    # Dry levels that can be chosen, sent as DryLev.
    dry_levels: tuple[int, ...] = ()
    # Fixed settings of an extra program.
    dry_level: int | None = None
    time_level: int | None = None


STANDARD_PROGRAMS = (
    # Listed first: the most used program.
    Program("eco_cotton", 14, dry_levels=(1, 2, 3, 4)),
    Program("daily_perfect_59", 1),
    Program("daily_45", 2),
    Program("eco_30", 3),
    Program("refresh", 4),
    Program("sport", 5),
    Program("relax_creases", 6),
    Program("small_load", 7),
    Program("wool", 8),
    Program("shirts", 9),
    Program("synthetics", 10, time_levels=_time_levels(13)),
    Program("darks", 11),
    Program("jeans", 12),
    Program("whites", 13, time_levels=_time_levels(20)),
)

EXTRA_PROGRAMS = (
    # Home care.
    Program("extra_bathrobe", 13, dry_level=4),
    Program("extra_tablecloths", 13, dry_level=3),
    Program("extra_anti_mites", 13, dry_level=4),
    Program("extra_bed_linen", 13, dry_level=4),
    Program("extra_delicates_antiallergy", 9, dry_level=2),
    Program("extra_delicate_tablecloths", 9, dry_level=2),
    Program("extra_backpacks", 10, time_level=7),
    Program("extra_curtains", 9, dry_level=2),
    Program("extra_duvet", 12, dry_level=4),
    # Special care.
    Program("extra_denim_jeans", 12, dry_level=4),
    Program("extra_easy_iron_cotton", 13, dry_level=1),
    Program("extra_shirts", 9, dry_level=2),
    Program("extra_cuddly_toys", 8),
    Program("extra_baby", 10, dry_level=3),
    Program("extra_technical_fabrics", 10, dry_level=2),
    Program("extra_swimsuits", 10, dry_level=2),
    Program("extra_playsuits", 9, dry_level=2),
    Program("extra_easy_iron_synthetics", 13, dry_level=1),
    Program("extra_warm_embrace", 3),
    Program("extra_dehumidifier", 3),
    Program("extra_gym_fit", 10, dry_level=2),
    Program("extra_lingerie", 9, dry_level=2),
    Program("extra_air_refresh", 3),
    Program("extra_waterproof", 3),
)

PROGRAMS = STANDARD_PROGRAMS + EXTRA_PROGRAMS
PROGRAMS_BY_KEY = {program.key: program for program in PROGRAMS}

# Name of each dial position reported by the dryer.
DIAL_POSITIONS = {
    0: "off",
    15: "remote",
    **{program.position: program.key for program in STANDARD_PROGRAMS},
}

# Delayed start choices, in minutes.
DELAYS = {"now": 0, **{f"h_{hours}": hours * 60 for hours in (1, 2, 3, 4, 6, 8, 12)}}

# Program to start until another one is chosen.
DEFAULT_PROGRAM = PROGRAMS_BY_KEY["eco_cotton"]
