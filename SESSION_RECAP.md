## 🧾 세션 회고 — 2026-07-10 17:48
**주제:** 에이전트 자가학습 시스템 MVP 구축

### ✅ 한 일
- 전에는 에이전트 결과를 평가·학습하는 체계가 없었음 → 이제 세션 종료 시 점수·피드백을 기록하고 학습 패턴을 추출하는 루프가 동작함
- 전에는 세션 마무리가 수확·위키·회고·이어가기 4단계뿐이었음 → 이제 0단계에서 에이전트 평가·학습 추출이 자동으로 선행됨
- 평가 스크립트(`log_evaluation`, `extract_learnings`, `apply_learning`)와 스펙·스킬이 `D:/.omc/agent-learning/`에 구축됨

### 🧭 정한 것
- 코드 벤치마크 루프(`self-improve`)와 세션 품질 학습(`agent-self-learning`)을 분리해 운영하기로 함

### 📂 손댄 파일
- `D:/.omc/specs/agent-self-learning.md` — 아키텍처 스펙
- `D:/.omc/agent-learning/scripts/` — 평가·추출·적용 CLI
- `C:/Users/ekth3/.cursor/skills/agent-self-learning/SKILL.md` — Cursor 스킬
- `session-closeout` 스킬 — 0단계 평가·학습 추가

### ⏭️ 다음 할 일
- SessionEnd 훅 자동 평가, approval-loop·work-cockpit 연동 등 후속 자동화
