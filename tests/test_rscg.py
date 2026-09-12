import json
from datetime import date

import pytest

from utils import rscg


def test_parse_dates_range() -> None:
    assert rscg.parse_dates("18-20 сентября", 2026) == (
        date(2026, 9, 18),
        date(2026, 9, 20),
    )


def test_extract_stages_payload_from_next_flight_chunk_with_embedded_quotes() -> None:
    payload = [
        {
            "id": 103,
            "round": 9,
            "dates": "18-20 сентября",
            "track": "Moscow Raceway",
            "location": "Московская обл.",
            "description": 'Два этапа в классе "Спортпрототип CN" за одни выходные!',
            "sprint": 'Спортпрототип CN (IV и V этап) "двойной"',
            "endurance": None,
            "additional": None,
            "note": None,
            "image": "/uploads/test.jpg",
            "ticketUrl": "https://tickets.example/?a=1&b=2",
            "infoUrl": "/stage-info",
            "isPast": False,
        }
    ]
    flight = '5:["$","$L1c",null,{"stages":' + json.dumps(payload, ensure_ascii=False) + '}]\n'
    html = f'<script>self.__next_f.push({json.dumps([1, flight], ensure_ascii=False)})</script>'

    parsed = rscg._extract_stages_payload(html)

    assert parsed == payload


@pytest.mark.asyncio
async def test_fetch_rscg_stages_parses_current_calendar() -> None:
    import aiohttp

    async with aiohttp.ClientSession() as session:
        stages = await rscg.fetch_rscg_stages(session)

    assert len(stages) >= 1
    assert all(stage.track for stage in stages)
