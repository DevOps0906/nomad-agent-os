---
name: stack-flutter
description: Flutter·Dart 3·Riverpod 3·go_router·drift 앱(키오스크·모바일) 작업 규약과 함정. 화면·상태·로컬 저장·기기 연동·플랫폼 채널 작업 전에 읽는다.
---

# stack-flutter

> Flutter·Riverpod·go_router·drift는 메이저 변경이 잦다. `pubspec.yaml` 실제 버전과 공식 문서를 확인한다.

## 30초 요약
1. 상태는 Riverpod, 화면 이동은 go_router, 로컬 저장은 drift. 프로젝트가 정한 폴더 구조를 따른다.
2. 기기(결제 단말·프린터·스캐너·카메라)는 인터페이스 패키지로만 부르고 가짜/진짜 구현을 설정으로 바꾼다.
3. 금액은 `int`(원). 나눗셈은 `~/`, 나머지는 규칙대로 한 사람에게.
4. 색·글자 크기·여백은 테마 토큰만. 위젯에 `Color(0x…)`·숫자 크기 직접 쓰기 금지.
5. 비동기 후 `context.mounted` / `ref.mounted` 확인.
6. 네트워크·기기는 끊긴다: outbox·재시도 대기열이 정상 경로. 실패는 결과 타입으로 받아 화면에 "다음 행동"을 보여 준다.
7. 반응형: 폰(~767) · 태블릿(768~1199) · 데스크톱/가로 태블릿(1200~) 레이아웃을 확인한다.

## 제출 전
- [ ] `q dart format --output=none --set-exit-if-changed .` · `q flutter analyze` · `q flutter test`
- [ ] `references/pitfalls.md` 훑기, 두 방향(가로·세로) 레이아웃 확인
