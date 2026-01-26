# Clawd Bot 개발 로드맵

> 마지막 업데이트: 2026-01-26

## 현재 상태 요약

### 구현 완료
- [x] Garmin 건강 데이터 동기화 (수면, 심박수, HRV, 스트레스, Body Battery)
- [x] PostgreSQL 데이터 저장 (`health_daily` 테이블)
- [x] Obsidian 마크다운 자동 생성
- [x] 텔레그램 봇 기본 명령어 (`/status`, `/brief`)
- [x] Docker Compose 오케스트레이션

### 미구현 (Stub)
- [ ] 운동 활동 데이터 수집 (`exercise_activity` 테이블 미사용)
- [ ] worker-brief (아침 브리핑)
- [ ] worker-notes (Obsidian 노트 관리)
- [ ] worker-monitor (컨테이너 모니터링)
- [ ] Redis 활용

---

## Phase 1: 단기 계획 (완료)

### 1.1 운동 데이터 수집 ✅
**목표**: Garmin Connect에서 운동 활동 데이터를 수집하여 DB에 저장

**구현 완료**:
- [x] `get_activities()` API로 최근 10개 운동 활동 조회
- [x] `exercise_activity` 테이블에 UPSERT
- [x] 운동 유형별 상세 정보 추출 (러닝, 사이클, 수영 등)
- [x] Obsidian `Exercise/` 폴더에 운동 로그 마크다운 생성
- [x] 페이스 변환 (m/s → min:sec/km)

**데이터 스키마**:
```sql
exercise_activity (
    activity_id BIGINT PRIMARY KEY,
    activity_type TEXT,           -- running, cycling, swimming
    activity_name TEXT,           -- 사용자 지정 이름
    start_time TIMESTAMP,
    duration_sec INTEGER,
    distance_meters NUMERIC,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_pace TEXT,                -- 러닝용 (min/km)
    calories INTEGER,
    elevation_gain NUMERIC,
    raw_data JSONB
)
```

### 1.2 worker-brief 구현 ✅
**목표**: 매일 아침 건강 브리핑 자동 전송

**구현 완료**:
- [x] 매일 오전 7시 / 오후 10시 텔레그램 알림
- [x] 어제 수면 요약 + 오늘 Body Battery 상태
- [x] 최근 운동 활동 요약 (최대 3개)
- [x] 컨디션 기반 동기부여 메시지

**알림 포맷**:
```
🌅 Good Morning!

😴 어제 수면: 7.2시간 (점수: 85)
🔋 Body Battery: 92% → 충전 완료!
💓 안정시 심박수: 58 bpm (HRV: BALANCED)
😰 평균 스트레스: 32

🏃 최근 운동:
  🏃 01/25 Morning Run: 5.2km (5:30/km)

---
✨ 오늘 컨디션 좋아 보여요! 좋은 하루 되세요!
```

### 1.3 기본 테스트 추가 ✅
**목표**: 핵심 기능에 대한 단위 테스트 작성

**구현 완료**:
- [x] pytest 기반 테스트 구조
- [x] Garmin 데이터 파싱 테스트
- [x] 마크다운 생성 테스트
- [x] DB 쿼리 구조 테스트
- [x] 샘플 데이터 fixtures

**구조**:
```
tests/
├── __init__.py
├── conftest.py              # 공통 fixtures
├── test_db.py               # DB 쿼리 테스트
├── test_garmin_parser.py    # Garmin 파싱 테스트
└── test_markdown_generator.py  # 마크다운 생성 테스트
```

### 1.4 에러 핸들링 강화 ✅
**목표**: 안정적인 운영을 위한 에러 처리 개선

**구현 완료**:
- [x] Garmin 로그인 실패 시 재시도 (최대 3회, 지수 백오프)
- [x] DB 연결 실패 시 자동 재연결 (retry decorator)
- [x] 에러 발생 시 텔레그램 알림
- [x] 동기화 완료 시 에러 요약 리포트

---

## Phase 2: 중기 계획

### 2.1 외부 서비스 연동
| 서비스 | 용도 | 우선순위 |
|--------|------|----------|
| Google Calendar | 일정 조회 → 브리핑 포함 | 높음 |
| Weather API | 날씨 정보 → 브리핑 포함 | 높음 |
| GitHub | 커밋/PR 현황 → 개발 브리핑 | 중간 |

### 2.2 Redis 활용
- 최근 조회 데이터 캐싱
- Garmin API Rate Limiting 대응
- 작업 큐 (비동기 처리)

### 2.3 worker-notes 구현
- Obsidian 데일리 노트 자동 생성
- 템플릿 기반 노트 구조화
- 태그 자동 추가

### 2.4 worker-monitor 구현
- Docker 컨테이너 헬스 체크
- 디스크/메모리 사용량 모니터링
- 이상 감지 시 알림

---

## Phase 3: 장기 계획

### 3.1 AI 기반 인사이트
- 주간/월간 건강 트렌드 분석
- 수면 패턴 ↔ 운동 상관관계
- 개인화된 건강 조언 생성

### 3.2 예측 알림
- 수면 부족 예측 → 일찍 자라는 알림
- 스트레스 증가 추세 → 휴식 권고
- 운동 패턴 기반 다음 운동 추천

### 3.3 음성 인터페이스
- Telegram 음성 메시지 지원
- TTS로 브리핑 읽어주기

### 3.4 대시보드
- 웹 기반 건강 대시보드
- 시각화 차트 (수면, 운동, 심박수 추이)

---

## 기술 스택

### 현재
- Python 3.10
- PostgreSQL 15
- Redis (미사용)
- Docker Compose
- python-telegram-bot 20.7
- garminconnect >= 0.2.38

### 추가 예정
- pytest (테스트)
- structlog (구조화 로깅)
- httpx (비동기 HTTP)
- openai / anthropic (AI 인사이트)

---

## 마일스톤

| 마일스톤 | 목표 | 상태 |
|----------|------|------|
| M1: 운동 데이터 | 운동 활동 수집 및 저장 | ✅ 완료 |
| M2: 아침 브리핑 | worker-brief 완성 | ✅ 완료 |
| M3: 테스트 | 핵심 기능 테스트 커버리지 70% | ✅ 완료 |
| M4: 안정화 | 에러 핸들링 및 모니터링 | ✅ 완료 |
| M5: 외부 연동 | Calendar + Weather 연동 | ⏳ 대기 |
| M6: AI 인사이트 | 트렌드 분석 기능 | ⏳ 대기 |

---

## 참고 자료

- [Clawd.bot 공식 사이트](https://clawd.bot)
- [Garmin Connect API (garminconnect 라이브러리)](https://github.com/cyberjunky/python-garminconnect)
- [python-telegram-bot 문서](https://python-telegram-bot.readthedocs.io/)
