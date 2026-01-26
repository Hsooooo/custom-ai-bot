# Clawd Bot 개발 로드맵

> 마지막 업데이트: 2026-01-26

## 현재 상태 vs 목표

### 현재 아키텍처 (Phase 1-2)
```
[Schedule] ─→ [Worker] ─→ [Data Collection] ─→ [Telegram Notification]
                              │
                              ▼
                         [Database]
```
**문제점**: AI 모델 개입 없음. 단순 스케줄 기반 자동화.

### 목표 아키텍처 (Phase 3+)
```
[User Message] ─→ [AI Agent Core] ─→ [Intent Recognition]
                        │                    │
                        ▼                    ▼
                   [LLM (Claude)]      [Skill Matching]
                        │                    │
                        ▼                    ▼
                  [Tool Selection] ←─ [Skills Registry]
                        │
                        ▼
              ┌─────────┴─────────┐
              ▼                   ▼
         [Execute Tool]    [Generate Response]
              │                   │
              ▼                   ▼
         [Data/Action]      [Natural Reply]
```
**핵심**: LLM이 중심에서 의도를 파악하고, 적절한 도구/스킬을 선택하여 실행.

---

## Gap Analysis: 현재 vs Clawdbot

| 영역 | 현재 프로젝트 | Clawdbot | Gap |
|------|--------------|----------|-----|
| **의사결정** | 스케줄 기반 (cron) | LLM 기반 (실시간) | 🔴 Critical |
| **인터페이스** | 명령어 (`/brief`) | 자연어 대화 | 🔴 Critical |
| **기능 확장** | 코드 수정 필요 | Skills (마크다운) | 🟡 Major |
| **도구 호출** | 하드코딩 | AI가 동적 선택 | 🔴 Critical |
| **메모리** | 없음 | Persistent Memory | 🟡 Major |
| **자기 개선** | 불가능 | 스킬 자동 생성 | 🟢 Nice-to-have |

---

## Phase 1-2: 완료 (Data Foundation)

### 구현 완료
- [x] Garmin 건강 데이터 동기화
- [x] 운동 활동 데이터 수집
- [x] PostgreSQL 데이터 저장
- [x] Obsidian 마크다운 자동 생성
- [x] 텔레그램 봇 기본 명령어
- [x] 외부 서비스 연동 (Weather, Calendar, GitHub)
- [x] Redis 캐싱 & Rate Limiting
- [x] worker-notes, worker-monitor

**이 단계의 가치**: AI Agent가 활용할 **데이터 인프라** 구축 완료.

---

## Phase 3: AI Agent Core (NEW)

> **목표**: LLM 기반 오케스트레이션 엔진 구축

### 3.1 Agent Brain 구현

**핵심 컴포넌트**:
```
agent/
├── core/
│   ├── agent.py           # Main Agent orchestrator
│   ├── llm_client.py      # Claude/OpenAI API wrapper
│   ├── intent_parser.py   # Intent recognition
│   └── response_gen.py    # Natural response generation
│
├── memory/
│   ├── conversation.py    # Conversation history
│   ├── user_prefs.py      # User preferences
│   └── semantic_search.py # Vector-based memory search
│
└── router/
    ├── skill_router.py    # Skill selection logic
    └── tool_router.py     # Tool execution router
```

**Agent Flow**:
```python
# Pseudo-code
async def handle_message(user_message: str) -> str:
    # 1. Load context
    context = await memory.get_relevant_context(user_message)

    # 2. Ask LLM to decide action
    decision = await llm.decide(
        message=user_message,
        context=context,
        available_skills=skills.list_all(),
        available_tools=tools.list_all()
    )

    # 3. Execute if action needed
    if decision.requires_action:
        result = await execute_skill_or_tool(decision)
        context.add_result(result)

    # 4. Generate natural response
    response = await llm.generate_response(
        message=user_message,
        context=context,
        action_result=result
    )

    # 5. Update memory
    await memory.save_conversation(user_message, response)

    return response
```

**LLM 선택 전략**:
| 작업 유형 | 모델 | 비용/속도 |
|----------|------|----------|
| 단순 질문/인사 | Claude Haiku | 저비용/빠름 |
| 데이터 조회/분석 | Claude Sonnet | 중간 |
| 복잡한 추론/계획 | Claude Opus | 고비용/정확 |

### 3.2 Skills System 구현

**스킬 구조** (Clawdbot 방식):
```
skills/
├── health/
│   ├── SKILL.md              # 스킬 정의
│   └── scripts/
│       └── query_health.py   # 실행 스크립트
│
├── exercise/
│   ├── SKILL.md
│   └── scripts/
│       └── analyze_runs.py
│
├── calendar/
│   ├── SKILL.md
│   └── scripts/
│       └── get_events.py
│
└── system/
    ├── SKILL.md
    └── scripts/
        └── server_status.py
```

**SKILL.md 예시** (건강 데이터 조회):
```markdown
---
name: health-query
description: |
  Query and analyze health data from Garmin.
  Use when user asks about sleep, heart rate, stress, body battery,
  or any health-related questions.
triggers:
  - "수면"
  - "심박수"
  - "스트레스"
  - "body battery"
  - "건강"
  - "어제 얼마나 잤어"
  - "요즘 컨디션"
---

## Instructions

When the user asks about health data:

1. **Identify the time range**
   - "어제" → yesterday
   - "이번주" → last 7 days
   - "지난달" → last 30 days
   - Default: last 3 days

2. **Identify the metrics**
   - 수면: sleep_hours, sleep_score
   - 심박: resting_hr, hrv_status
   - 스트레스: stress_level
   - 에너지: body_battery_max, body_battery_min

3. **Execute query**
   Run: `python scripts/query_health.py --days={N} --metrics={metrics}`

4. **Analyze and respond**
   - Compare to user's baseline
   - Identify trends
   - Provide actionable insights

## Example Interactions

User: "어제 잠 잘 잤어?"
→ Query sleep data for yesterday
→ Compare to 7-day average
→ "어제 7.2시간 주무셨네요. 평소(6.8시간)보다 좋았어요! 수면 점수도 85점으로 양호합니다."

User: "요즘 스트레스 어때?"
→ Query stress for last 7 days
→ Analyze trend
→ "지난 일주일 평균 스트레스는 38로, 2주 전(45)보다 개선됐어요. 수면이 좋아진 영향인 것 같습니다."
```

### 3.3 Tool Orchestration

**도구 레지스트리**:
```python
TOOLS = {
    "query_database": {
        "description": "Query PostgreSQL for health/exercise data",
        "parameters": ["query", "params"],
        "handler": db_query_handler
    },
    "fetch_garmin": {
        "description": "Fetch latest data from Garmin Connect",
        "parameters": ["data_type", "date_range"],
        "handler": garmin_fetch_handler
    },
    "send_notification": {
        "description": "Send Telegram notification",
        "parameters": ["message", "parse_mode"],
        "handler": telegram_send_handler
    },
    "write_obsidian": {
        "description": "Create or update Obsidian note",
        "parameters": ["path", "content"],
        "handler": obsidian_write_handler
    },
    "web_search": {
        "description": "Search the web for information",
        "parameters": ["query"],
        "handler": web_search_handler
    },
    "execute_shell": {
        "description": "Execute shell command (with approval)",
        "parameters": ["command"],
        "handler": shell_handler
    }
}
```

**AI Tool Calling Flow**:
```
User: "최근 러닝 기록 분석해줘"
           │
           ▼
    [LLM Decision]
    "이 요청을 처리하려면 query_database 도구로
     exercise_activity 테이블을 조회해야 함"
           │
           ▼
    [Tool Execution]
    query_database(
        query="SELECT * FROM exercise_activity
               WHERE activity_type='running'
               ORDER BY start_time DESC LIMIT 10"
    )
           │
           ▼
    [Result Processing]
    LLM이 결과 데이터를 분석하고 인사이트 생성
           │
           ▼
    [Natural Response]
    "최근 10회 러닝 기록을 분석했어요:
     - 평균 거리: 5.2km
     - 평균 페이스: 5:45/km (점점 좋아지는 중!)
     - 주 2-3회 꾸준히 뛰고 계시네요 👍"
```

### 3.4 Persistent Memory

**메모리 구조**:
```
memory/
├── conversations/        # 대화 기록
│   └── 2026-01-26.json
├── user_profile.json     # 사용자 프로필/선호도
├── learned_facts.json    # 학습된 사실들
└── embeddings/           # 벡터 검색용 임베딩
    └── index.faiss
```

**메모리 활용**:
```python
# 사용자 프로필 예시
{
    "name": "한수",
    "preferences": {
        "language": "ko",
        "briefing_time": "07:00",
        "running_goal": "sub-25min 5K",
        "sleep_target": 7.5
    },
    "baseline_metrics": {
        "avg_sleep": 6.8,
        "avg_rhr": 58,
        "avg_stress": 35
    },
    "learned_facts": [
        "월요일에 주로 러닝함",
        "커피 마시면 수면 점수 떨어짐",
        "스트레스 높으면 HRV 낮아짐"
    ]
}
```

---

## Phase 4: Advanced AI Features

### 4.1 Proactive Intelligence

**자동 인사이트 생성**:
```python
# 매일 데이터 분석 후 자동 알림
async def daily_intelligence():
    # 1. 오늘 데이터 vs 최근 평균 비교
    anomalies = detect_anomalies(today_data, baseline)

    # 2. 패턴 인식
    patterns = analyze_patterns(last_30_days)

    # 3. LLM에게 인사이트 생성 요청
    if anomalies or patterns.new_discoveries:
        insight = await llm.generate_insight(
            anomalies=anomalies,
            patterns=patterns,
            user_context=user_profile
        )
        await send_proactive_notification(insight)
```

**예측 알림**:
```
# 수면 부족 예측
"어제 5.5시간밖에 못 주무셨네요.
오늘 저녁은 일찍 쉬시는 게 좋겠어요.
평소 패턴상 이런 날 다음 날 스트레스가 올라가더라고요."

# 운동 추천
"지난 3일간 Body Battery가 90% 이상 유지됐어요.
오늘 컨디션 좋을 때 러닝 어떠세요?
최근 페이스로 보면 5K 25분 도전해볼 만해요!"
```

### 4.2 Self-Improvement (스킬 자동 생성)

**대화를 통한 스킬 생성**:
```
User: "Todoist에서 오늘 할 일 가져와줘"

Agent: "Todoist 연동 스킬이 없네요. 만들어드릴까요?"

User: "응, 만들어줘"

Agent: [Todoist API 문서 조회]
       [스킬 마크다운 생성]
       [스크립트 작성]
       [테스트 실행]

       "Todoist 스킬을 만들었어요! 이제 할 일을 물어보시면
        바로 가져올 수 있어요. 테스트해볼까요?"
```

### 4.3 Multi-Modal Support

**음성 인터페이스**:
```
[Telegram Voice] ─→ [Whisper STT] ─→ [Agent] ─→ [TTS] ─→ [Voice Reply]
```

**이미지 분석**:
```
User: [식단 사진 전송]
Agent: [Vision API로 음식 인식]
       "점심으로 샐러드 드셨네요! 약 350kcal 정도로 보여요.
        오늘 운동 계획이 있으시면 탄수화물을 조금 더 드셔도 좋을 것 같아요."
```

---

## Phase 5: Ecosystem & Integration

### 5.1 확장 가능한 스킬 마켓플레이스

```
skills-community/
├── finance/          # 가계부, 지출 분석
├── smart-home/       # 홈 자동화
├── productivity/     # Notion, Linear, Todoist
├── media/            # Spotify, Jellyfin
└── dev-tools/        # GitHub, CI/CD
```

### 5.2 Multi-Agent Collaboration

```
[Main Agent] ─→ [Health Specialist Agent]
             ─→ [Productivity Agent]
             ─→ [DevOps Agent]
```

---

## Implementation Priorities

### Milestone 9: Agent Brain (우선순위 1)
- [ ] LLM Client 구현 (Claude API)
- [ ] Intent Parser 구현
- [ ] 기본 대화 처리 로직
- [ ] Telegram 자연어 인터페이스

### Milestone 10: Skills System (우선순위 2)
- [ ] Skill Registry 구현
- [ ] SKILL.md 파서
- [ ] 기본 스킬 3개 생성 (health, exercise, calendar)
- [ ] Skill Router 구현

### Milestone 11: Tool Orchestration (우선순위 3)
- [ ] Tool Registry 구현
- [ ] 기존 기능을 Tool로 래핑
- [ ] AI Tool Calling 구현
- [ ] 결과 처리 및 응답 생성

### Milestone 12: Memory System (우선순위 4)
- [ ] 대화 기록 저장
- [ ] 사용자 프로필 관리
- [ ] 벡터 검색 (선택사항)

### Milestone 13: Proactive Intelligence (우선순위 5)
- [ ] 이상치 감지
- [ ] 패턴 분석
- [ ] 자동 인사이트 알림

---

## 기술 스택 변경

### 추가 예정
| 카테고리 | 기술 | 용도 |
|----------|------|------|
| LLM API | anthropic | Claude API 클라이언트 |
| LLM API | openai (optional) | GPT 폴백 |
| Embeddings | sentence-transformers | 벡터 검색 |
| Vector Store | faiss / chromadb | 메모리 검색 |
| STT | openai-whisper | 음성 인식 |
| TTS | edge-tts | 음성 합성 |

### 새로운 환경 변수
```bash
# AI API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # Optional fallback

# Model Selection
DEFAULT_MODEL=claude-3-5-sonnet
FAST_MODEL=claude-3-5-haiku
SMART_MODEL=claude-3-opus

# Memory
ENABLE_VECTOR_SEARCH=true
MEMORY_RETENTION_DAYS=90
```

---

## 마일스톤 업데이트

| 마일스톤 | 목표 | 상태 |
|----------|------|------|
| M1-M8 | Phase 1-2 (Data Foundation) | ✅ 완료 |
| M9 | Agent Brain | ⏳ 대기 |
| M10 | Skills System | ⏳ 대기 |
| M11 | Tool Orchestration | ⏳ 대기 |
| M12 | Memory System | ⏳ 대기 |
| M13 | Proactive Intelligence | ⏳ 대기 |
| M14 | Voice Interface | ⏳ 대기 |
| M15 | Self-Improvement | ⏳ 대기 |

---

## 참고 자료

- [Clawdbot 공식 사이트](https://clawd.bot)
- [Clawdbot GitHub](https://github.com/clawdbot/clawdbot)
- [Clawdbot Skills 문서](https://docs.clawd.bot/tools/skills)
- [Anthropic Claude API](https://docs.anthropic.com)
- [Clawdbot 사용 사례](https://kristianfreeman.com/how-i-use-clawdbot)
- [How Clawdbot Works (MacStories)](https://www.macstories.net/stories/clawdbot-showed-me-what-the-future-of-personal-ai-assistants-looks-like/)
