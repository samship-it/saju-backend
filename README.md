# saju-backend

만세력 사주 엔진 + Gemini 자연어 콘텐츠 레이어. FastAPI 기반 REST API.

- **엔진(`core/`)**: 결정론적 파이썬 계산(만세력·대운·십신·신살·용신 등) — AI 개입 없음, 사람마다 항상 같은 입력이면 같은 출력.
- **콘텐츠(`domains/*/data/*.json`)**: 대부분의 도메인은 "**일주 × 조건**" 조합별 자연어 해석을 **사전 생성해 정적 JSON DB로 저장**해두고, 런타임에는 키로 조회만 한다(Gemini 호출 없음 → 응답 0.1초대, 비용 0, 사람마다 일관된 결과). 일부(오늘의 운세 실시간 보정, 오늘의 재테크, 타로)는 여전히 런타임에 Gemini를 호출한다.
- 정적 DB는 **연도 하드코딩이 없다** — 세운/대운은 60갑자 순환이라 "일주×세운" 또는 "일주×대운순번" 키만으로 결정되고, 특정 연도(2026/2027/…)는 그 키로 즉시 재사용된다.

## 목차

- [아키텍처](#아키텍처)
- [디렉토리 구조](#디렉토리-구조)
- [core/ · shared/ — 공용 엔진·유틸](#core--shared--공용-엔진유틸)
- [도메인별 역할](#도메인별-역할)
- [정적 콘텐츠 DB 생성 스크립트](#정적-콘텐츠-db-생성-스크립트-scriptsgenerate_content_dbpy)
- [환경변수](#환경변수)
- [로컬 실행](#로컬-실행)
- [배포](#배포)
- [알려진 제약 · TODO](#알려진-제약--todo)

## 아키텍처

```
요청 → main.py (FastAPI 앱, 라우터 등록)
     → domains/<domain>/router.py   (Pydantic 요청 검증)
     → domains/<domain>/service.py  (비즈니스 로직)
         ├─ core/*                  (원국·대운·십신 등 결정론적 계산)
         ├─ domains/<domain>/content_db.py  (정적 JSON 조회 — 대부분 여기서 끝)
         └─ shared/ai_client.py     (정적 DB가 없는 일부 도메인만 런타임 Gemini 호출)
```

## 디렉토리 구조

```
saju-backend/
├── main.py               # FastAPI 앱 생성, 라우터 등록(prefix/tags), CORS, 타로 이미지 정적 서빙
├── config.py              # .env 로드, GEMINI_MODEL_NAME / API_SECRET_KEY
├── core/                  # 사주 계산 엔진 (AI 없음)
├── shared/                 # 공용 유틸 (AI 클라이언트, 캐시, 프롬프트 조립, 텍스트 포맷)
├── domains/                # 도메인별 router.py + service.py (+ content_db.py + data/*.json)
│   ├── saju/  daily/  wealth/  personality/  compatibility/
│   ├── relationship/  yearly/  lifelong/  tarot/  market/
│   └── comprehensive/     # ⚠️ 미사용 — main.py 에 연결 안 된 레거시 빈 디렉토리
├── scripts/
│   └── generate_content_db.py   # 정적 콘텐츠 DB 생성기 (아래 참고)
├── tests/                  # pytest (testpaths=tests, pytest.ini)
├── local_saju.db            # 로컬 SQLite (캐시/시장 요약 테이블)
└── requirements.txt / requirements-dev.txt
```

## core/ · shared/ — 공용 엔진·유틸

| 모듈 | 역할 |
|---|---|
| `core/saju_base.py` | 만세력/원국 계산(연월일시주, 대운 등) — 모든 도메인의 출발점 |
| `core/daewoon.py` | 대운 순번별 사실(`daewoon_step_facts`), 월운 리스트 |
| `core/constants.py` | 간지 공용 상수 테이블(한자 기준) |
| `core/sipsin.py` | 십신(十神) 계산 |
| `core/sinsal.py` | 신살(神殺) 계산 |
| `core/strength.py` | 일간 강약 · 억부 용신/희신/기신 · 기본 격국 · 배우자성 |
| `core/twelve_unseong.py` | 12운성 계산 |
| `core/interactions.py` | 지지 상호작용: 합·충·형·파·해·삼합·방합 |
| `core/domain_derived.py` | 분야별 파생 데이터 · 작용 강도 지표 |
| `core/timeframe.py` | 날짜/기간 계산 헬퍼(3개월 전략, 결혼운 10년 창) — **연도 하드코딩 금지** 원칙 |
| `core/database.py` | SQLAlchemy 모델(`DailyFortuneCache`, `FortuneCache`, `MarketSummary`) — `DATABASE_URL` 미설정 시 로컬 SQLite |
| `core/gemini_client.py` | 레거시 진입점, `shared.ai_client`로 위임 |
| `shared/ai_client.py` | Gemini 자연어 생성 공용 클라이언트(모델/키 처리) |
| `shared/fortune_cache.py` | 운세 결과 캐시 헬퍼(`get_or_create`) |
| `shared/persona_map.py` | 일간(말투 베이스) + 일지(표현 보정) 페르소나 |
| `shared/public.py` | API 응답에 실을 사주 요약(`person_summary`) |
| `shared/saju_prompt.py` | 사주 정밀 데이터 → Gemini 프롬프트 입력 블록 직렬화 |
| `shared/text_format.py` | AI 서술형 출력을 문단으로 다듬기(`paragraphize`) |

## 도메인별 역할

| 도메인 | prefix | 엔드포인트 | 과금 | 콘텐츠 소스 | 규모 |
|---|---|---|---|---|---|
| `saju` | `/api/v1/saju` | `POST /chart` | 무료 | 엔진 계산만(AI 없음) | – |
| `daily` | `/api/v1/daily` | `POST /fortune` | 무료(기본운세) | **정적 DB** (`daily_db.json`) | 일주×일진 3,600 |
| `wealth` | `/api/v1/wealth` | `POST /analysis` | 무료(DAILY) | **런타임 Gemini** (시장 스냅샷 + 사주 결합) | – |
| `personality` | `/api/v1/personality` | `POST /character`, `POST /aptitude` | 각 30P | **정적 DB** (`personality_db.json`) | 일주 60 |
| `compatibility` | `/api/v1/compatibility` | `POST /analyze` | 60P | **정적 DB** (`compatibility_db.json`) | 일주쌍 3,600 |
| `relationship` | `/api/v1/relationship` | `POST /reunion`, `/crush`, `/marriage` | 각 30P | **정적 DB** (`relationship_db.json` + `reunion_charm_db.json`/`crush_charm_db.json`) | 10,980 + 60×2 |
| `yearly` | `/api/v1/yearly` | `GET /categories`, `POST /{category}` (총운/재물/연애/사업/직장이직/학업/건강/여행/취미) | 무료 | **정적 DB** (`yearly_<category>_db.json`, 카테고리별 파일) | 카테고리당 3,600 (학업만 10,800) — 연도 무관(세운 60갑자 재사용) |
| `lifelong` | `/api/v1/lifelong` | `POST /analysis` | 250P | **정적 DB** (`lifelong_base/domains/stage_db.json` 3파일) | 60 + 2,400 + 14,000 |
| `tarot` | `/api/v1/tarot` | `GET /cards`, `POST /read` | 무료/타로 이용권 | **런타임 Gemini** | – |
| `market` | (라우터 없음, `wealth`가 내부 호출) | – | – | `domains/market/cron_market.py` — KRX 정규장 시간 판정 + DB 스냅샷/중립 문구 스텁 | 실시간 시세 fetch **미구현**(아래 제약 참고) |
| `comprehensive` | – | – | – | ⚠️ 빈 디렉토리, `main.py`에 미등록 — 사용하지 않음 |

### 도메인 내부 3계층 패턴 (정적 DB 도메인 공통)

```
router.py      # Pydantic 요청 모델 + HTTPException 래핑
service.py     # core/* 로 원국·대운 계산 → content_db.lookup(키) → 없으면 폴백 텍스트
content_db.py  # data/*.json 을 프로세스 시작 시 1회 메모리 로드, 키로 조회만
```
`is_fallback` 필드가 `true`면 해당 키가 정적 DB에 없어 고정 폴백 문구가 나간 것 — 정상 동작이지만 DB 커버리지 이슈를 의미하니 발견 시 `scripts/generate_content_db.py`로 해당 키를 채워야 한다.

## 정적 콘텐츠 DB 생성 스크립트 (`scripts/generate_content_db.py`)

일주×조건 조합별로 Gemini에게 텍스트를 미리 생성시켜 `domains/<domain>/data/*.json`에 저장하는 배치 도구. 4,000줄 단일 스크립트, 도메인마다 `run_<domain>()` 함수 + 공통 실행기(`_run_batched`/`_run_batched_concurrent`)로 구성.

### 기본 사용법

```bash
python scripts/generate_content_db.py --domain <도메인> [옵션...]
```

### `--domain` 전체 목록

| 값 | 대상 |
|---|---|
| `daily` | 오늘의 운세 (일주×일진 3,600) |
| `personality` | 성격/적성 (일주 60) |
| `relationship` | 재회/짝사랑/결혼운 (10,980, `--limit`으로 청크 진행) |
| `reunion_charm` / `crush_charm` | 재회운·짝사랑운 "나의 매력" (일주 60) |
| `marriage_extras` | 결혼운 couple 3,600에 확인사항·미래시나리오 2필드 추가 |
| `marriage_solo` | 결혼운 solo(상대 미지정) |
| `compatibility` | 궁합 (일주쌍 3,600, `--limit`) |
| `yearly_overall` / `yearly_overall_extras` | 연간 총운 3,600(+기회/주의 달·치트키·쥐약 4필드) |
| `yearly_business` / `yearly_career_change` / `yearly_study` / `yearly_health` / `yearly_travel` / `yearly_hobby` / `yearly_wealth` / `yearly_love` | 연간 분야운 8종 |
| `lifelong_base` | 평생운세 일주당 life_theme (60) |
| `lifelong_domains` | 평생운세 삶의 4대영역 (2,400) |
| `lifelong_stage` | 평생운세 대운 8단계 흐름 (14,000) |

### 주요 옵션

| 옵션 | 설명 |
|---|---|
| `--limit N` | 이번 실행에서 새로 생성할 최대 개수 (0=제한 없음) |
| `--only <키>` | 특정 키 하나만 생성 (예: `--only 戊辰_乙巳`) |
| `--overwrite` | 이미 있는 키도 다시 생성 |
| `--out <경로>` | 출력 JSON 경로 override (기본: 도메인별 `data/*.json`) |
| `--model <이름>` | 이 모델 하나만 사용(모델 순환 끔) |
| `--no-model-rotate` | 모델 순환 없이 `GEMINI_MODEL_NAME` 하나만 사용 |
| `--regen-stale` | 이미 있으나 최우선 모델로 안 만들어진 항목만 재생성 |
| `--delay <초>` | 호출 간 대기 (기본 1.0초) |
| `--max-retries N` | 호출당 최대 재시도 (기본 5) |
| `--max-days N` | 일일 한도 소진 시 최대 며칠까지 자정 대기 후 자동 재개할지 (기본 10) |
| `--dry-run` | 실제 생성 없이 대상 목록만 출력 |
| `--batch N` | 1회 호출당 N개 조합 배치 생성(비용/요청수 절감). **권장 10**. `gemini-3.5-flash-lite` 계열 고정 사용, `--workers`보다 우선 적용 |
| `--workers N` | 병렬 워커 수(기본 1=순차). 2 이상이면 동시 생성 — **키 개수보다 많아도 됨**: `worker_id % len(keys)`로 키를 순환 배정해 여러 워커가 한 키를 나눠 쓰는 오버구독 방식 |

### 자주 쓰는 예시

```bash
# 특정 도메인, 대상만 미리 확인 (실제 호출 없음)
python scripts/generate_content_db.py --domain lifelong_stage --dry-run

# 배치+병렬 조합으로 전량 생성 (권장 조합: batch 10 + workers 10)
python -u scripts/generate_content_db.py --domain lifelong_stage --workers 10 --batch 10

# 특정 키 하나만 재생성
python scripts/generate_content_db.py --domain daily --only 戊辰_乙巳 --overwrite

# 이미 있는데 구모델로 만들어진 항목만 최신 모델로 정리
python scripts/generate_content_db.py --domain personality --regen-stale
```

### 동작 특성 (재실행 안전)

- **재개 가능**: 이미 있는 키는 건너뛰므로 중단 후 같은 명령으로 재실행하면 이어서 진행된다.
- **원자적 저장**: 매 호출 성공마다 `_atomic_write_json`으로 즉시 디스크에 반영 — 중간에 죽어도 그때까지 생성분은 보존된다.
- **키 로테이션**: `GEMINI_API_KEY` + `GEMINI_API_KEY_1`, `_2`, … 를 순서대로 모아 순환 사용. 단기(분당) 429는 다음 키로 회전, 일일(PerDay) 한도 소진 키는 죽이고 나머지로 계속하다가 전부 소진되면 태평양시 자정까지 대기 후 자동 재개(`--max-days`까지).
- **모델 폴백 순서**: `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → `gemini-flash-lite-latest` (배치 모드 기준, `DAILY_BATCH_MODELS`).

## 환경변수

| 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `GEMINI_API_KEY` | 사실상 필수 | – | Gemini 기본 API 키. 런타임 도메인(wealth/tarot 등)과 생성 스크립트 공통 사용 |
| `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, … | 선택 | – | 생성 스크립트(`generate_content_db.py`) 전용 추가 키 — 병렬/키 로테이션용. 번호 순서대로 수집 |
| `GEMINI_MODEL_NAME` | 선택 | `gemini-3.5-flash-lite` | 런타임 Gemini 호출 시 사용할 기본 모델 |
| `INTERNAL_API_KEY` | 선택 | `default-secret-key` | `/api/v1/daily/fortune` 전용 `x-api-key` 헤더 검증값(`config.API_SECRET_KEY`). 나머지 엔드포인트는 키 검사 안 함 |
| `DATABASE_URL` | 선택 | `sqlite:///./local_saju.db` | SQLAlchemy 연결 문자열(캐시·시장요약 테이블) |
| `TAROT_IMAGE_DIR` | 선택 | `domains/tarot/타로이미지` | 타로 이미지 정적 서빙 디렉토리(`/static/tarot_images`) |
| `<DOMAIN>_DB_PATH` (예: `DAILY_DB_PATH`, `PERSONALITY_DB_PATH`, `COMPATIBILITY_DB_PATH`, `RELATIONSHIP_DB_PATH`, `REUNION_CHARM_DB_PATH`, `CRUSH_CHARM_DB_PATH`, `LIFELONG_BASE_DB_PATH`, `LIFELONG_DOMAINS_DB_PATH`, `LIFELONG_STAGE_DB_PATH`) | 선택 | 도메인별 `data/*.json` | 정적 DB 파일 경로 override (테스트/임시 분리용) |
| `YEARLY_<CATEGORY>_DB_PATH` (예: `YEARLY_OVERALL_DB_PATH`, `YEARLY_WEALTH_DB_PATH`, …) | 선택 | `data/yearly_<category>_db.json` | yearly 카테고리별 DB 경로 override |

`.env` 는 프로젝트 루트(`saju-backend/.env`)에 두면 `config.py`의 `_load_dotenv()`가 자동 로드한다(이미 설정된 OS 환경변수는 덮어쓰지 않음 — 배포 환경변수가 항상 우선).

## 로컬 실행

```bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn main:app --reload
# http://localhost:8000/docs 에서 Swagger UI 확인
```

테스트:
```bash
pytest   # pytest.ini: testpaths=tests
```

## 배포

- 백엔드: GitHub `samship-it/saju-backend` → Render, main 브랜치 push 시 자동 배포. 운영 URL은 프론트 `.env`의 `VITE_API_BASE_URL` 참고.
- 프론트: 별도 레포 `samship-it/today-score-magic` (`VITE_API_BASE_URL`로 백엔드 지정).
- 저장소 루트(`운세/`, 이 저장소의 상위 폴더)에 오래된 백엔드 체크아웃이 남아있으나 실제 배포 대상이 아니므로 무시할 것.

## 알려진 제약 · TODO

- **`domains/comprehensive/`**: `main.py`에 등록되지 않은 빈 레거시 디렉토리 — 실질적으로 미사용.
- **`domains/market/`**: 실제 시세 API(Yahoo Finance 등) 연동이 아직 없음. `cron_market.py`는 KRX 정규장 시간 여부만 판정하고, 지수 값(`indices.KOSPI/NASDAQ/BTC`)은 항상 `None`을 반환하는 스텁이다. `market_point`(시황 한 줄)도 DB에 저장된 스냅샷이 없으면 중립 고정 문구로 대체된다. 프론트(`today-score-magic`)의 지수 요약 칩도 현재 하드코딩된 예시 값이며, 서비스 오픈(실서비스 전환) 전 실제 연동이 필요하다.
- **`is_fallback: true` 모니터링**: 정적 DB 도메인에서 폴백이 뜬다는 건 해당 키가 아직 생성 안 됐다는 신호 — 발견 시 `scripts/generate_content_db.py --domain <도메인> --only <키>`로 채울 것.
