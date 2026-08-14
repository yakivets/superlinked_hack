"""The device sends an agent id string and the backend looks it up by name, so a
drift between the two lists means the wrong agent silently handles a meeting.
This test reads the firmware source and fails on drift."""

import re
from pathlib import Path

from app.agents import AGENT_ORDER

FIRMWARE = Path(__file__).resolve().parents[2] / "firmware" / "ui.cpp"


def _parse_array(name: str) -> list[str]:
    src = FIRMWARE.read_text(encoding="utf-8")
    m = re.search(rf"{name}\[\]\s*=\s*\{{(.*?)\}};", src, re.S)
    assert m, f"{name} not found in {FIRMWARE}"
    return re.findall(r'"([^"]+)"', m.group(1))


def test_firmware_agent_ids_match_backend_order():
    assert _parse_array("AGENT_IDS") == AGENT_ORDER


def test_firmware_agent_count_matches():
    src = FIRMWARE.read_text(encoding="utf-8")
    m = re.search(r"AGENT_COUNT\s*=\s*(\d+)", src)
    assert m and int(m.group(1)) == len(AGENT_ORDER)


def test_firmware_has_a_name_for_every_id():
    assert len(_parse_array("AGENT_NAMES")) == len(AGENT_ORDER)
