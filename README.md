# IR Journal Digest

JVIR(J Vasc Interv Radiol)와 CVIR(Cardiovasc Intervent Radiol) 최신 논문을
매월 자동으로 가져와 **AI로 한글 요약**하고 **GitHub Pages**에 게시하는 개인용 시스템.

**로컬 GPU 모드** (기본값): Ollama + qwen2.5:14b — 인터넷 연결·API 키 불필요  
**클라우드 모드**: Google Gemini API — `config.py`에서 `USE_LOCAL_LLM = False` 설정

간담도/비혈관 인터벤션 관련 논문은 상세 요약 + 비판적 코멘트가 추가됩니다.

---

## 기능

- PubMed E-utilities API로 최근 30일 색인 논문 자동 수집
- Google Gemini 2.0 Flash로 한글 요약 (의학 용어 한글/영어 병기)
- 관심 분야(간담도·비혈관 인터벤션) 자동 분류 → 2단계 키워드 + AI 확인
- 관심 논문: 상세 결과 + 비판적 코멘트 + 임상 적용 추가
- 모바일 반응형 + 다크모드 HTML 사이트 생성 (Tailwind CSS)
- 저널별·월별 아카이브, 인페이지 검색
- 매월 1일 자동 실행 (GitHub Actions cron), 수동 실행 지원
- 재실행 시 이미 요약된 PMID 스킵 (증분 실행)

---

## 빠른 시작

### 모드 선택

`src/config.py`에서 LLM 모드를 선택합니다:

```python
USE_LOCAL_LLM = True   # 로컬 GPU (Ollama) — 기본값
USE_LOCAL_LLM = False  # 클라우드 (Gemini API)
```

---

### 로컬 GPU 모드 (Ollama)

#### GPU 요구사항
- VRAM 10GB 이상 (RTX 3080 / RTX 4070 이상 권장)
- RAM 16GB 이상

#### 1. Ollama 설치

https://ollama.com/download 에서 Windows용 설치 파일 다운로드 후 설치.

#### 2. 모델 다운로드

```bash
ollama pull qwen2.5:14b
```

다운로드 약 9GB. 한 번만 받으면 이후 오프라인에서도 사용 가능.

#### 3. 로컬 실행

```bash
pip install -r requirements.txt
python -m src.main
```

Ollama는 별도로 `ollama serve`를 실행하거나, 백그라운드 서비스로 자동 실행됩니다.

#### 4. Windows 작업 스케줄러로 자동 실행

매월 1일 자동 실행 설정:

1. **작업 스케줄러** 열기 (Win + S → "작업 스케줄러" 검색)
2. **작업 만들기** 클릭
3. **일반** 탭: 이름 `IR Journal Digest`, "사용자가 로그온할 때만 실행" 선택
4. **트리거** 탭 → **새로 만들기**:
   - 시작: 매월, 1일, 오전 9:00
5. **동작** 탭 → **새로 만들기**:
   - 동작: 프로그램 시작
   - 프로그램: `C:\path\to\python.exe`  *(또는 `python`)*
   - 인수: `-m src.main`
   - 시작 위치: `C:\project\ir-journal-digest`
6. **확인** 후 암호 입력

---

### 클라우드 모드 (Gemini API)

#1. https://aistudio.google.com 접속 후 Google 계정으로 로그인
2. **Get API key → Create API key** 클릭 (무료 티어: 분당 15회, 일 1,500회)
3. `src/config.py`에서 `USE_LOCAL_LLM = False` 설정

#### 3. GitHub Secrets 등록 (Gemini 모드, GitHub Actions 사용 시)

레포지토리 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 값 | 필수 |
|---|---|---|
| `GEMINI_API_KEY` | Gemini API 키 | 필수 |
| `NCBI_API_KEY` | NCBI API 키 (rate limit 완화) | 선택 |

NCBI API 키: https://www.ncbi.nlm.nih.gov/account/ 에서 무료 발급.

### 3. GitHub Pages 활성화

레포지토리 → **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: `main` / folder: `/docs`
- **Save** 클릭

약 1분 후 `https://<username>.github.io/<repo-name>/` 에서 확인.

### 4. 첫 실행 (시드 생성)

Actions 탭 → **Monthly IR Journal Digest** → **Run workflow** → **Run workflow** 클릭.

완료 후 Pages URL에서 결과를 확인하세요.

---

## 로컬 테스트

```bash
# 의존성 설치
pip install -r requirements.txt

# .env 파일 생성
cp .env.example .env
# .env 파일에 GEMINI_API_KEY 입력

# 실행
python -m src.main
```

생성된 HTML: `docs/index.html`, `docs/archive/YYYY-MM.html`

로컬에서 확인:
```bash
cd docs && python -m http.server 8000
# http://localhost:8000 접속
```

---

## 수동 실행

GitHub Actions 탭 → **Monthly IR Journal Digest** → **Run workflow**.

---

## 키워드 수정

`src/config.py`에서 관심 분야 키워드를 수정하세요.

```python
# 간담도 키워드 추가 예시
HEPATOBILIARY_KEYWORDS = [
    ...,
    "portal vein embolization",
    "liver metastasis",
]

# 비혈관 키워드 추가 예시
NONVASCULAR_KEYWORDS = [
    ...,
    "vertebroplasty",
    "kyphoplasty",
]
```

키워드 매칭 후 Gemini가 2차 확인하므로 false positive가 줄어듭니다.

---

## 파일 구조

```
.
├── .github/workflows/monthly-digest.yml  # 자동화 워크플로우
├── src/
│   ├── config.py          # 모델명, 키워드, 저널 설정 (USE_LOCAL_LLM 포함)
│   ├── fetch_pubmed.py    # PubMed E-utilities API
│   ├── gemini_client.py   # Gemini API 래퍼 (재시도, 지수 백오프)
│   ├── ollama_client.py   # Ollama 로컬 LLM 래퍼 (GPU 모드)
│   ├── classify.py        # 2단계 관심 분야 분류
│   ├── summarize.py       # 요약 프롬프트 + Pydantic 검증
│   ├── render.py          # Jinja2 HTML 렌더링
│   └── main.py            # 메인 오케스트레이션
├── templates/
│   ├── index.html.j2      # 아카이브 인덱스 템플릿
│   └── month.html.j2      # 월별 논문 목록 템플릿
├── static/style.css       # 커스텀 CSS
├── data/                  # YYYY-MM.json (논문 + 요약 원본)
├── docs/                  # 생성된 HTML (GitHub Pages)
├── logs/                  # 실행 로그 (gitignore됨)
├── requirements.txt
├── .env.example
└── README.md
```

---

## 비용

| 항목 | 비용 |
|---|---|
| PubMed E-utilities | 무료 |
| Gemini 2.0 Flash (무료 티어) | 무료 (분당 15회, 일 1,500회 한도) |
| GitHub Actions | 무료 (월 2,000분 한도) |
| GitHub Pages | 무료 |

월 1회 실행 시 논문 수가 약 30~80편이면 Gemini 무료 한도 내에서 처리 가능합니다.

---

## 트러블슈팅

**`limit: 0, model: gemini-2.0-flash` 에러 (무료 한도 0)**

`gemini-2.0-flash`는 2026년부터 무료 티어 한도가 0으로 변경되었습니다.
`src/config.py`에서 모델을 변경하세요:

```python
GEMINI_MODEL: str = "gemini-2.5-flash"  # 또는 아래 표 참고
```

2026년 5월 실측 기준:

| 모델 | 무료 한도 | 특징 |
|---|---|---|
| `gemini-1.5-flash` | **1500회/일** | **권장: 안정적, 한도 넉넉** |
| `gemini-1.5-flash-8b` | 1500회/일 | 가볍고 빠름, 품질 소폭 낮음 |
| `gemini-2.5-flash` | 20회/일 | 프리뷰 제한 (사실상 사용 불가) |
| `gemini-2.0-flash` | **0회/일** | 유료 전용 (사용 불가) |

또는 `.env` 파일에서 일회성으로 override:
```
GEMINI_MODEL=gemini-2.5-flash-lite
```

**Rate limit 초과 시**
- `src/gemini_client.py`의 `_INTER_CALL_DELAY`를 `1.0` 이상으로 늘리세요.
- NCBI_API_KEY를 등록하면 PubMed rate limit이 완화됩니다.

**JSON 파싱 실패 시**
- `data/YYYY-MM.json`에서 해당 항목의 `"summary"` 필드에 `"_raw"`, `"_error"` 키로 raw 텍스트가 저장됩니다.
- 해당 항목의 `"summary"` 필드를 `null`로 바꾼 뒤 재실행하면 다시 시도합니다.

**특정 논문 재요약**
- `data/YYYY-MM.json`에서 해당 PMID 항목의 `"summary"` 필드를 `null`로 설정 후 재실행.

**GitHub Pages가 업데이트되지 않을 때**
- `docs/` 폴더에 `.nojekyll` 파일이 있는지 확인 (자동 생성됨).
- Pages 설정에서 branch/folder가 올바른지 확인.
