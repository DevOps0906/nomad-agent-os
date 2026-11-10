#!/usr/bin/env python3
"""bm-calc — BM 결정론 계산기(Decimal). 공식은 BM_METHOD 정본과 동일."""
import json
import sys
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, getcontext

getcontext().prec = 28

EXAMPLE = {
    "name": "BookForge", "currency": "KRW", "target_ratio": 3, "fixed_cost": 3000000,
    "plans": [{
        "name": "Pro", "price": 29000,
        "variable_costs": {"AI API": 5500, "결제수수료": 1000, "CS": 2200},
        "churn": 0.05, "cac": 90000}],
    "scenarios": [
        {"name": "보수", "plan": "Pro", "override": {"variable_cost": 11000, "churn": 0.09, "fixed_cost": 4000000}},
        {"name": "기준", "plan": "Pro", "override": {}},
        {"name": "낙관", "plan": "Pro", "override": {"variable_cost": 7000, "churn": 0.03, "fixed_cost": 2500000}}],
    "score": {
        "axes": [
            {"name": "시장성", "max": 20, "score": 14, "evidence": "D", "note": "타깃 명확, 시장 규모 근거 보강 필요"},
            {"name": "수익성", "max": 20, "score": 16, "evidence": "E", "note": "공헌이익률 70%, LTV/CAC 3배 설계"},
            {"name": "검증도", "max": 20, "score": 4, "evidence": "E", "note": "인터뷰·사전예약 전"},
            {"name": "실행가능성", "max": 20, "score": 17, "evidence": "E", "note": "1인 + AI 자동화"},
            {"name": "확장성", "max": 20, "score": 16, "evidence": "E", "note": "화이트라벨·교육 연계"}],
        "blocking": []},
}


def D(v):
    return Decimal(str(v))


def rnd(v, places=0):
    if v is None:
        return None
    return D(v).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def calc_plan(name, price, variable, churn, fixed, cac, ratio):
    price, variable, churn, fixed, ratio = D(price), D(variable), D(churn), D(fixed), D(ratio)
    warn = []
    cm = price - variable
    r = {"name": name, "price": price, "variable_cost": variable, "contribution": cm,
         "margin": cm / price if price else None, "churn": churn, "fixed_cost": fixed,
         "ltv": None, "cac_cap": None, "cac": None, "ltv_cac": None, "payback": None, "bep": None}
    if cm <= 0:
        warn.append(f"{name}: 공헌이익 {cm} ≤ 0 — 팔수록 손해, LTV·BEP 계산 불가")
    else:
        r["bep"] = int((fixed / cm).to_integral_value(rounding=ROUND_CEILING))
        if churn > 0:
            r["ltv"] = cm / churn
            r["cac_cap"] = r["ltv"] / ratio
        if cac is not None:
            r["cac"] = D(cac)
            r["payback"] = r["cac"] / cm
            if r["ltv"] is not None and r["cac"] > 0:
                r["ltv_cac"] = r["ltv"] / r["cac"]
    if churn <= 0:
        warn.append(f"{name}: 이탈률 0 — LTV 무한대, 계산하지 않음(이탈률 가정 필요)")
    r["warnings"] = warn
    return r


def score_result(score):
    axes = score.get("axes", [])
    total = sum((D(a["score"]) for a in axes), Decimal(0))
    maxv = sum((D(a["max"]) for a in axes), Decimal(0))
    warn = []
    for a in axes:
        if D(a["score"]) > D(a["max"]):
            warn.append(f"점수 축 {a['name']}: 점수가 만점을 넘음")
        if not a.get("evidence"):
            warn.append(f"점수 축 {a['name']}: 증거 등급 없음")
    blocking = score.get("blocking", [])
    t = total * 100 / maxv if maxv else Decimal(0)
    if t >= 80:
        verdict = "MVP 개발·지원사업 신청"
    elif t >= 60:
        verdict = "부족한 축 추가 검증(6단계로)"
    elif t >= 40:
        verdict = "노코드 MVP로 축소"
    else:
        verdict = "보류·폐기"
    if blocking:
        verdict = "보류(blocking 조건: " + ", ".join(blocking) + ")"
    return {"axes": axes, "total": total, "max": maxv, "verdict": verdict, "blocking": blocking, "warnings": warn}


def compute(data):
    ratio = data.get("target_ratio", 3)
    fixed = data.get("fixed_cost", 0)
    plans, by_name, warnings = [], {}, []
    for p in data.get("plans", []):
        var = p.get("variable_cost")
        if var is None:
            var = sum((D(v) for v in p.get("variable_costs", {}).values()), Decimal(0))
        r = calc_plan(p["name"], p["price"], var, p.get("churn", 0), p.get("fixed_cost", fixed), p.get("cac"), ratio)
        plans.append(r); by_name[p["name"]] = (p, r); warnings += r["warnings"]
    scenarios = []
    for s in data.get("scenarios", []):
        p, base = by_name[s["plan"]]
        o = s.get("override", {})
        r = calc_plan(s["name"], o.get("price", p["price"]), o.get("variable_cost", base["variable_cost"]),
                      o.get("churn", base["churn"]), o.get("fixed_cost", base["fixed_cost"]), o.get("cac", p.get("cac")), ratio)
        scenarios.append(r); warnings += r["warnings"]
    sc = score_result(data["score"]) if data.get("score") else None
    if sc:
        warnings += sc["warnings"]
    return {"name": data.get("name", ""), "currency": data.get("currency", "KRW"), "target_ratio": D(ratio),
            "plans": plans, "scenarios": scenarios, "score": sc, "warnings": warnings}


def fmt(v, places=0, pct=False):
    if v is None:
        return "-"
    if pct:
        return f"{rnd(v * 100, 1)}%"
    return f"{rnd(v, places):,}"


def render(res):
    out = [f"# BM 계산 결과 — {res['name']} (통화 {res['currency']}, 목표 LTV/CAC {res['target_ratio']}배)", ""]
    out += ["## 플랜별 단위경제", "",
            "| 플랜 | 가격 | 변동비 | 공헌이익 | 공헌이익률 | 이탈률 | LTV | CAC 상한 | 실CAC | LTV/CAC | 회수(월) | BEP(명) |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["plans"]:
        out.append(f"| {r['name']} | {fmt(r['price'])} | {fmt(r['variable_cost'])} | {fmt(r['contribution'])} | {fmt(r['margin'], pct=True)} | "
                   f"{fmt(r['churn'], pct=True)} | {fmt(r['ltv'])} | {fmt(r['cac_cap'])} | {fmt(r['cac'])} | "
                   f"{fmt(r['ltv_cac'], 2)} | {fmt(r['payback'], 1)} | {fmt(r['bep'])} |")
    if res["scenarios"]:
        out += ["", "## 시나리오 (override 적용)", "",
                "| 시나리오 | 가격 | 변동비 | 이탈률 | 고정비 | 공헌이익 | LTV | BEP(명) |", "|---|---|---|---|---|---|---|---|"]
        for r in res["scenarios"]:
            out.append(f"| {r['name']} | {fmt(r['price'])} | {fmt(r['variable_cost'])} | {fmt(r['churn'], pct=True)} | "
                       f"{fmt(r['fixed_cost'])} | {fmt(r['contribution'])} | {fmt(r['ltv'])} | {fmt(r['bep'])} |")
    sc = res["score"]
    if sc:
        out += ["", "## 사업성 점수", "", "| 축 | 만점 | 점수 | 증거 등급 | 근거 |", "|---|---|---|---|---|"]
        for a in sc["axes"]:
            out.append(f"| {a['name']} | {a['max']} | {a['score']} | {a.get('evidence', '-')} | {a.get('note', '')} |")
        out.append(f"| **합계** | {fmt(sc['max'])} | **{fmt(sc['total'])}** | | 판정: {sc['verdict']} |")
    if res["warnings"]:
        out += ["", "## 경고", ""] + [f"- {w}" for w in res["warnings"]]
    out += ["", "> 단순 LTV는 이탈률 일정 가정. 모든 값은 입력 가정에서 나온 계산이며 검증된 사실이 아니다."]
    return "\n".join(out)


def to_jsonable(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, dict):
        return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [to_jsonable(v) for v in o]
    return o


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("사용: bm-calc <input.json> [--json] | bm-calc --init [파일]")
        return 0 if argv else 1
    if argv[0] == "--init":
        path = argv[1] if len(argv) > 1 else "bm-input.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(EXAMPLE, f, ensure_ascii=False, indent=2)
        print(f"예시 입력 생성: {path}")
        return 0
    with open(argv[0], encoding="utf-8") as f:
        data = json.load(f)
    res = compute(data)
    print(json.dumps(to_jsonable(res), ensure_ascii=False, indent=2) if "--json" in argv else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
