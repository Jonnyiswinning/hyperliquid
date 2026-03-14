from __future__ import annotations

from solbot.connectors.hyperliquid import MarketDataAdapter


class _FakeClient:
    def __init__(self, book: dict) -> None:
        self._book = book

    def l2_book(self, coin: str) -> dict:
        return self._book

    def candles(self, coin: str, interval: str, start_ms: int, end_ms: int):
        return []


def test_spread_and_depth_with_dict_levels() -> None:
    client = _FakeClient(
        {
            "levels": [
                [{"px": "101.0", "sz": "12.5", "n": 2}],
                [{"px": "101.1", "sz": "9.0", "n": 3}],
            ]
        }
    )
    adapter = MarketDataAdapter(client, "SOL", "1m")

    spread = adapter.spread_bps()
    depth = adapter.top_depth()

    assert 0 < spread < 20
    assert depth == 9.0


def test_spread_and_depth_with_list_levels() -> None:
    client = _FakeClient({"levels": [[[101.0, 7.0]], [[101.2, 8.0]]]})
    adapter = MarketDataAdapter(client, "SOL", "1m")
    assert adapter.top_depth() == 7.0
    assert adapter.spread_bps() > 0
