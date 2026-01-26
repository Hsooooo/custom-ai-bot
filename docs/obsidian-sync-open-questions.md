# Obsidian Sync / iCloud Sync 미결사항 정리

## 현재 상태
- VPS에서 `custom-ai-bot`이 Obsidian vault 마크다운을 생성함
  - 경로(호스트): `/home/ubuntu/custom-ai-bot/obsidian_vault/`
  - 생성 주체: `worker-garmin` (Health/Exercise), `worker-notes` (Daily/Weekly 등)
- 이 vault는 **VPS 로컬 디스크에만 존재**하며, iCloud/Obsidian Sync로 사용자 디바이스(아이폰/맥)로 자동 동기화되지 않음.

## 요구사항/선호
- 사용자는 **iCloud Drive 내 vault로 동기화**하는 경험을 선호함.
- 다만 **맥을 상시 켜둘 수 없음** → "맥을 브릿지 허브로 두고 VPS→맥→iCloud/Sync" 방식은 지연/누락 가능성이 큼.

## 핵심 문제
- iCloud Drive는 서버(Linux VPS)가 공식적으로 안정적으로 마운트/동기화할 수 있는 방식이 제한적임.
- Obsidian Sync는 공식 앱 중심(디바이스) 동기화가 강점이며, VPS가 직접 Sync의 "클라이언트"가 되기 어렵거나 비권장됨.

## 가능한 대안 (검토 필요)

### A) 현상유지: VPS vault는 서버에만, 디바이스 동기화는 별도
- 장점: 운영 단순, 안정적
- 단점: 서버가 만든 노트가 자동으로 디바이스에 반영되지 않음

### B) 브릿지 디바이스 사용 (맥)
- VPS → (주기적 pull/rsync) → Mac의 vault → Obsidian Sync/iCloud
- 장점: iCloud/Sync 경험 유지
- 단점: 맥 상시 가동이 어려워 자동화에 부적합

### C) 서버 친화 저장소를 동기화 채널로 사용
- Nextcloud/WebDAV/S3/B2/Git 등
- VPS는 생성된 vault를 위 채널로 push
- 디바이스는 해당 채널을 기반으로 vault를 사용(또는 pull)
- 장점: 서버 자동화와 궁합이 좋음
- 단점: iOS에서 "완전 자동"은 채널/앱에 따라 제약이 있을 수 있음

### D) Obsidian Sync를 사용하되, 서버 생성물은 다른 경로로 소비
- 예: Obsidian Sync vault는 사용자가 유지
- 서버는 브리핑/요약 등만 메시지로 제공하거나, 파일은 별도 링크/아카이브로 제공
- 장점: Sync는 그대로 안정
- 단점: "서버가 만든 노트가 vault에 자동으로 들어오는" 목표와 다름

## 결정해야 할 질문
1. 정말로 "서버에서 생성된 markdown"이 iOS Obsidian vault에 **자동 반영**되어야 하는가?
2. iCloud Drive 기반 동기화를 꼭 유지해야 하는가, 아니면 Nextcloud/S3 같은 서버 친화 채널로 전환 가능한가?
3. 집에 24/7로 켜둘 수 있는 장치(NAS/Raspberry Pi 등)가 있는가? 있다면 브릿지로 사용 가능.
4. 보안/프라이버시 요구 수준: 건강 데이터가 제3자 클라우드(S3/B2/Nextcloud hosted)에 저장되는 것이 허용되는가?

## 제안 (초안)
- "자동"이 최우선이면: **서버 친화 채널(Nextcloud/S3 등)** 로 전환하는 쪽이 가장 현실적.
- iCloud 경험이 최우선이면: 맥이 상시 켜질 수 없으므로 자동화 기대치를 낮추거나, 24/7 브릿지 장치를 준비.
