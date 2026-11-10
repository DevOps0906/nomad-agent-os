import importlib.util
from decimal import Decimal
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bm_calc", ROOT / "global/nomad/bin/py/bm_calc.py")
bm = importlib.util.module_from_spec(spec); spec.loader.exec_module(bm)


class BmCalc(unittest.TestCase):
    def setUp(self):
        self.res = bm.compute(bm.EXAMPLE)

    def test_bookforge_base(self):
        p = self.res["plans"][0]
        self.assertEqual(p["contribution"], 20300)
        self.assertEqual(p["margin"], Decimal("0.7"))
        self.assertEqual(p["ltv"], 406000)
        self.assertEqual(bm.rnd(p["cac_cap"]), 135333)
        self.assertEqual(p["bep"], 148)
        self.assertEqual(bm.rnd(p["ltv_cac"], 2), Decimal("4.51"))

    def test_scenarios(self):
        c, b, o = self.res["scenarios"]
        self.assertEqual((c["bep"], bm.rnd(c["ltv"])), (223, 200000))
        self.assertEqual(b["bep"], 148)
        self.assertEqual((o["bep"], bm.rnd(o["ltv"])), (114, 733333))

    def test_score_and_blocking(self):
        sc = self.res["score"]
        self.assertEqual(sc["total"], 67)
        self.assertIn("추가 검증", sc["verdict"])
        d = dict(bm.EXAMPLE); d["score"] = dict(d["score"], blocking=["실결제 0건"])
        self.assertTrue(bm.compute(d)["score"]["verdict"].startswith("보류"))

    def test_warnings(self):
        d = {"plans": [{"name": "X", "price": 100, "variable_cost": 120, "churn": 0.1}]}
        self.assertTrue(any("공헌이익" in x for x in bm.compute(d)["warnings"]))
        d = {"plans": [{"name": "Y", "price": 100, "variable_cost": 20, "churn": 0}]}
        self.assertTrue(any("이탈률 0" in x for x in bm.compute(d)["warnings"]))

    def test_render(self):
        self.assertIn("| Pro |", bm.render(self.res))


if __name__ == "__main__":
    unittest.main()
