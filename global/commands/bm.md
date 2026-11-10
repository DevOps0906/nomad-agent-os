---
description: 사업모델(BM) 7단계(고객→가치→가격→단위경제→파트→린 검증→점수)를 수행
---
`bm-model` 스킬 절차로 진행한다. 대상 제품: $ARGUMENTS

1. 저장 위치 확인: 기본은 BM-CORE `projects/<제품>/BM.md`(방법 정본 `method/BM_METHOD.md`, 캔버스는 `canvas/BMC_TEMPLATE.md`를 복사해 `projects/<제품>/canvas.md`), BM-CORE가 없으면 `docs/plan/BM.md`. 없으면 스킬의 `templates/bm.md`로 만든다. 제품 방향·가격 미결은 사용자에게 묻는다.
2. 1~3단계(고객·가치·가격): `planner`에게 위임(근거 경로만 전달). 가격 근거는 경쟁 단가로 적는다.
3. 4단계: 팀장이 입력을 확정하고 `~/.claude/nomad/bin/bm-calc --init bm-input.json` → 값 교체 → `bm-calc bm-input.json`. 모델이 숫자를 직접 계산하지 않는다. 경고는 문서에 옮긴다.
4. 5~6단계(파트·공통비, 린 검증): `planner`에게 위임. 통과 기준은 실험 전에 숫자로 확정한다.
5. 7단계: 팀장이 점수 입력(`score.axes`·`blocking`)을 채우고 `bm-calc`로 합계·판정을 얻는다. 각 축을 증거(등급 A~E, 출처 경로)에 연결한다. E 등급뿐인 점수는 낮춘다.
6. `reviewer`(mode=doc)로 모순·근거 없는 수치·증거 미연결을 점검하고 반영한다. 반영 후 숫자가 바뀌면 `bm-calc`를 다시 실행한다.
7. 사용자에게 판정(80/60/40 구간)·blocking 여부·다음 검증 행동을 3줄로 보고한다.
