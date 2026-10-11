from __future__ import annotations

import unittest

from fpga2asic.trace import compare_axi_transactions, compare_signal_records


class TraceComparisonTests(unittest.TestCase):
    def test_signal_comparison_is_cycle_exact(self) -> None:
        golden = [{"cycle": 1, "q": "0"}, {"cycle": 2, "q": "1"}]
        same = [{"cycle": 1, "q": "0"}, {"cycle": 2, "q": "1"}]
        shifted = [{"cycle": 1, "q": "0"}, {"cycle": 3, "q": "1"}]
        self.assertTrue(compare_signal_records(golden, same).matched)
        self.assertFalse(compare_signal_records(golden, shifted).matched)

    def test_axi_comparison_ignores_legal_timing_and_cross_id_interleave(self) -> None:
        golden = [
            {"event": "read_rsp", "cycle": 10, "id": 1, "data": "11", "resp": 0},
            {"event": "read_rsp", "cycle": 11, "id": 2, "data": "22", "resp": 0},
        ]
        candidate = [
            {"event": "read_rsp", "cycle": 30, "id": 2, "data": "22", "resp": 0},
            {"event": "read_rsp", "cycle": 40, "id": 1, "data": "11", "resp": 0},
        ]
        self.assertTrue(compare_axi_transactions(golden, candidate).matched)

    def test_axi_comparison_detects_data_change(self) -> None:
        golden = [{"event": "write", "id": 1, "addr": "10", "data": "aa"}]
        candidate = [{"event": "write", "id": 1, "addr": "10", "data": "ab"}]
        self.assertFalse(compare_axi_transactions(golden, candidate).matched)


if __name__ == "__main__":
    unittest.main()

