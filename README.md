# docs_reader

*한국어 · [English README](README.en.md)*

LLM 기반 문서 구조화 추출 CLI. PDF · Office(docx/xlsx/pptx, 레거시 ppt/doc/xls) ·
이미지/스캔본 · **HWP(한글)** 에서 정해진 **스키마(필드)** 를 뽑아 검증된 **JSON** 으로 만듭니다.
(HWP는 pyhwp `hwp5html`로 직접 파싱 — LibreOffice가 실패하는 정부 HWP도 처리. 레거시 ppt/doc/xls·hwpx는 LibreOffice 변환.)

두 가지 설계 원칙:

- **오픈소스 우선, 프로바이더 중립.** 기본 백엔드는 OpenAI 호환 엔드포인트(vLLM/Ollama/…)로 서빙하는
  오픈 모델. Gemini·Claude는 저신뢰 필드에 대한 **선택적 에스컬레이션/교차검증**으로만 사용.
- **품질 우선 = 다중 패스 파이프라인.** 단일 LLM 호출이 아니라
  **① 스캔/이미지/HWP는 오픈 OCR·레이아웃(Stage A) → ② self-consistency 구조화 추출(Stage B) →
  ③ 검증(LLM-as-judge)·신뢰도·저신뢰 게이트 재추출(Stage C)** 로 정확도를 끌어올립니다.

## 설치

`requirements.txt`(pip) 또는 `pyproject.toml` extras 중 편한 쪽:

```bash
python -m venv .venv && source .venv/bin/activate

# 방법 A) requirements.txt — 코어 + 기본 오픈소스 백엔드
pip install -r requirements.txt
pip install -e .                 # CLI(docs-reader) 등록
# 개발용: pip install -r requirements-dev.txt

# 방법 B) pyproject extras
pip install -e ".[openai]"       # 오픈소스/OpenAI 호환 백엔드 (기본)
pip install -e ".[ocr]"          # Stage A OCR (rapidocr, 한국어/CPU)
pip install -e ".[gemini]"       # Gemini 에스컬레이션
pip install -e ".[claude]"       # Claude 에스컬레이션
pip install -e ".[hwp]"          # HWP(한글) 직접 파싱 (pyhwp)
pip install -e ".[all,dev]"      # 전체 + pytest
```

시스템 의존성: **LibreOffice (`soffice`)** — Office/HWP → PDF 변환에 필요.
(`apt install libreoffice` / `brew install --cask libreoffice`)

### 설정 (.env)

`.env.example` 를 `.env` 로 복사해 값을 채우면 실행 시 자동 로드됩니다(python-dotenv).
쉘 환경변수가 항상 `.env` 보다 우선합니다.

```bash
cp .env.example .env
```

주요 변수: `DOCS_READER_BASE_URL`, `DOCS_READER_TEXT_MODEL`, `DOCS_READER_VISION_MODEL`,
`DOCS_READER_OCR`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`.

## 오픈소스 백엔드 서버 (기본)

OpenAI 호환 엔드포인트면 무엇이든 됩니다. 예) Ollama:

```bash
ollama serve
ollama pull gemma3:4b                     # 텍스트 추출용 (디폴트, 종합 최고 성능)
ollama pull qwen2.5vl:7b                  # 비전(스캔/이미지)용
export DOCS_READER_BASE_URL=http://localhost:11434/v1
```

**디폴트 모델은 `gemma3:4b`** (내부 벤치 종합 1위: 정확도 96.7%, 한국어 100%). `DOCS_READER_TEXT_MODEL` 로 교체 가능.
vLLM·LM Studio·OpenRouter도 `--base-url`/`DOCS_READER_BASE_URL`만 바꾸면 동일하게 동작합니다.

### GPU (CUDA)

`--cuda` 플래그 하나로 GPU를 씁니다 — GPU Ollama를 **자동으로 :11500에 기동**하고 그쪽으로 라우팅합니다.

```bash
docs-reader extract 문서.pdf --schema schemas/invoice.py --cuda
docs-reader providers                     # GPU 서버/모델 상태 확인
```

- 시스템 Ollama가 **snap**이라 GPU를 못 잡는 환경에서도, snap 번들 바이너리+CUDA 라이브러리를 sudo 없이 snap 밖에서 실행해 GPU를 사용합니다(모델은 재사용). 수동 기동: `bash tools/ollama_gpu.sh`.
- 항상 GPU를 쓰려면 `.env`에 `DOCS_READER_CUDA=1`. 다른 GPU 엔드포인트는 `--base-url` 로 지정.
- 실측: RTX 4070 Ti SUPER에서 CPU 대비 **3~4배 빠름** (동일 정확도).

## 한국어 특화 (권장)

한국어 품질은 두 층에서 결정됩니다.

**1) OCR (스캔·이미지·HWP)** — 기본 `rapidocr`는 한국어가 약해, 한국어 특화 OCR을 권장합니다.

```bash
pip install -e ".[ocr-korean]"     # PaddleOCR-korean (권장)  또는
pip install -e ".[ocr-easyocr]"    # EasyOCR (설치 간단)
docs-reader extract 스캔.pdf --schema schemas/invoice.py --ocr korean
```

`--ocr korean` 은 PaddleOCR-korean → EasyOCR(ko) 순으로 사용 가능한 엔진을 자동 선택합니다.
(`--ocr paddle` / `--ocr easyocr` 로 직접 지정, `--ocr-lang` 로 언어 변경.)

**2) 추출 LLM** — 한국어 특화 오픈모델로 교체(프로바이더 중립이라 모델 태그만 바꾸면 됨):

| 용도 | 한국어 특화 오픈모델(예) |
| --- | --- |
| 텍스트 | EXAONE 3.5 (LG) · SOLAR (Upstage) · Qwen2.5(한국어 양호) |
| 비전(문서) | VARCO-VISION (NCSOFT, 한국어 문서 특화) · Qwen2.5-VL |

```bash
ollama pull exaone3.5:7.8b
export DOCS_READER_TEXT_MODEL=exaone3.5:7.8b
# 비전 모델도 DOCS_READER_VISION_MODEL 로 지정 (예: varco-vision)
```

에스컬레이션의 Gemini/Claude도 한국어가 강하므로, 저신뢰 필드에 `--escalate` 로 교차검증하면
한국어 정확도를 추가로 끌어올릴 수 있습니다.

## 사용

```bash
# 단일 문서 추출 (기본: 오픈소스 + 검증 패스)
docs-reader extract invoice.pdf --schema schemas/invoice.py -o out.json

# 로딩/라우팅만 확인 (LLM 호출 없음)
docs-reader extract scan.pdf --schema schemas/invoice.py --dry-run

# 품질 극대화: self-consistency 5표결 + 저신뢰 필드 상용 교차검증
docs-reader extract form.hwp --schema schemas/invoice.py \
    --samples 5 --escalate --min-confidence 0.8

# 디렉토리 일괄
docs-reader batch ./docs --schema schemas/invoice.py -o ./out

# 백엔드/자격 점검
docs-reader providers
```

주요 옵션: `--provider opensource|gemini|claude|mock`, `--model`, `--base-url`,
`--force-vision/--force-text`, `--office-vision`, `--ocr auto|rapidocr|docling|none`,
`--samples N`, `--verify/--no-verify`, `--escalate`, `--min-confidence`, `--data-only`,
`--tables/--no-tables`, `--extract-images`, `--images-dir DIR`, `--figures-vision`.

### 표 · 이미지 추출

- **표**: PDF는 PyMuPDF `find_tables`, Office는 표 API로 감지해 **Markdown 표**로 변환한 뒤
  LLM 입력 텍스트에 주입합니다(플랫 텍스트보다 표 필드 추출 정확도가 크게 향상). `--no-tables`로 끌 수 있음.
  스키마에 `line_items` 같은 배열 필드를 두면 표가 그대로 구조화 JSON으로 추출됩니다.
- **임베디드 이미지/도표**: `--extract-images`로 문서(PDF/docx/pptx/xlsx/HWP)에 박힌 이미지를
  파일로 뽑아 `--images-dir`(기본 `./extracted_images/<name>/`)에 저장하고, 출력 JSON의
  `meta.images`에 경로·페이지·크기를 기록합니다.
- **도표를 값으로 읽기**: `--figures-vision`을 주면 추출한 도표 이미지를 비전 모델에도 함께 넣어
  텍스트 문서 속 차트/그림의 값까지 추출을 시도합니다.

```bash
# 표를 line_items로 추출 + 로고/도표 이미지 파일로 추출
docs-reader extract report.pdf --schema schemas/invoice.py \
    --extract-images --images-dir ./out/imgs -o out.json
```

## 스키마 정의 (둘 다 지원)

- **Pydantic** (`.py`): 모델을 `Schema = YourModel` 로 지정(또는 파일에 모델 1개). 타입 검증·강제.
- **JSON Schema** (`.json`): 언어 무관. 파이썬 없이도 정의.
- **Few-shot**(선택): `이름.examples.json` 사이드카를 두면 추출 프롬프트에 예시로 주입.

예시는 `schemas/invoice.py`, `schemas/invoice.json`, `schemas/invoice.examples.json` 참고.

## 환각 제어

추출값의 환각(문서에 없는 값을 지어냄)을 능동적으로 제거합니다. 단순 신뢰도 표시가 아니라 **실제로 값을 null 처리**합니다.

- **기권 프롬프트**: "확실하지 않으면 null. 세상지식·추론으로 채우지 말 것."
- **판정 억제(Stage C)**: LLM-as-judge가 "원문에 근거 없음"으로 판정한 필드(`verify_confidence < 임계값`)를 제거.
- **결정론적 소스 그라운딩**: 추출한 스칼라 값이 원문(텍스트/OCR)에 실제로 존재하는지 확인. 숫자는 콤마·소수 형태까지 대조. 없으면 제거.
- 제거된 항목은 출력 `meta.dropped_hallucinations`에 사유(`judge_unsupported` / `not_in_source`)와 함께 기록.

옵션: `--drop-hallucinations/--keep-hallucinations`(기본 on), `--grounding/--no-grounding`, `--hallucination-threshold 0.5`.

**실측 예 (llama3.2:3b, 한국어 스캔)** — 소형 모델이 `currency`에 문자열 `"null"`을 환각 → 제어가 이중 탐지로 제거:

```json
"dropped_hallucinations": [
  {"field": "currency", "value": "null", "reasons": ["judge_unsupported(0.00)", "not_in_source"]}
]
```

## 정확도 평가

라벨 데이터셋(`<name>.<ext>` + `<name>.gold.json`, OCR은 `<name>.gold.txt`)에 대해
필드 정확도(정밀도/재현율/F1, 환각 수)와 OCR 정확도(CER/WER)를 측정합니다.

```bash
python tools/make_eval_dataset.py            # 예시 라벨 데이터셋 생성(eval/dataset)

# OCR 정확도만 (LLM 불필요) — 한국어 OCR 실측
docs-reader eval eval/dataset --schema schemas/invoice.py --ocr-only --ocr korean

# 필드 추출 정확도 (LLM 필요; 모델 서버/키 연결 후)
docs-reader eval eval/dataset --schema schemas/invoice.py --provider opensource -o report.json
```

**측정 지표**
- 필드: `field_accuracy`(정답=값 일치 + 빈값 일치), `precision`/`recall`/`f1`, `hallucinations`(정답이 빈값인데 값을 채운 수). 숫자·날짜·콤마·리스트(순서 무시)를 정규화 비교.
- OCR: `CER`(문자 오류율)/`WER`(단어 오류율) → `char_accuracy`/`word_accuracy`.

**실측 예 (이 저장소 PaddleOCR-korean, 한국어 스캔 인보이스)**

```text
[OCR] korean_scan.pdf  char_acc=100.0%  word_acc=71.4%
```

문자 인식은 100%, 단어 차이는 순수 띄어쓰기(한국어 띄어쓰기 편차)로 필드 추출에는 영향 없음.

### 벤치마크 결과

라벨 데이터셋(영문 텍스트 / 표 / 한국어 스캔 인보이스, 3문서 × 10필드)에서 오픈소스 모델별 필드 추출 정확도.
환경: RTX 4070 Ti SUPER(GPU), PaddleOCR-korean. 재현: `python tools/benchmark.py` (`tools/ollama_gpu.sh`로 GPU 서버).

| 모델 | 정확도 | 정밀도 | 재현율 | **F1** | 환각 | 시간(GPU) |
| --- | --- | --- | --- | --- | --- | --- |
| **gemma3:4b** (디폴트) | **96.7%** | 95.2 | 100.0 | **97.6** | 1 | 22.7s |
| exaone3.5:7.8b (LG 한국어) | 93.3% | 90.5 | 95.0 | 92.7 | 1 | 24.5s |
| qwen2.5:3b (가성비) | 93.3% | 90.5 | 95.0 | 92.7 | 1 | 23.7s |
| qwen2.5:7b-instruct | 90.0% | 86.4 | 95.0 | 90.5 | 2 | 25.3s |
| llama3.2:3b | 83.3% | 81.8 | 90.0 | 85.7 | 3 | 18.7s |
| llama3.1:8b | 80.0% | 76.2 | 80.0 | 78.0 | 2 | 23.5s |

**한국어 스캔 인보이스만** (필드 단위):

| 모델 | 정확도 | F1 | 비고 |
| --- | --- | --- | --- |
| gemma3:4b / qwen2.5:3b | **100%** | **100** | 전부 정답 |
| exaone3.5:7.8b | 90% | 83.3 | `currency` 원↔KRW 정규화 차이 |
| qwen2.5:7b | 90% | 92.3 | line_items 환각 |
| llama3.1:8b | 60% | 50 | 한국어 환각 심함 — 비추천 |

**GPU(CUDA) 속도** (3문서/모델, CPU → GPU): gemma3:4b 94.0s → **22.7s (4.1×)**, qwen2.5:7b 107.6s → **25.3s (4.3×)**,
llama3.1:8b 102.4s → **23.5s (4.4×)** — 정확도는 동일, 속도만 **3~4배**.

**환각 제어 효과** (raw → 그라운딩 제어): 환각 심한 모델은 정밀도가 오름(llama3.1: P 76.2→84.2, F1 78→82.1).
강한 모델은 의미상 정규화된 값(원→KRW)을 소폭 과제거할 수 있어, `--verify`(판정패스)와 함께 쓰는 것을 권장.

> 참고: 3문서 소규모 벤치입니다. 실제 공문서(HWP/과업지시서)로 확정하려면 해당 문서에 정답 라벨을 붙여 재측정하세요.

## 아키텍처

```text
파일 → loaders(하이브리드) ── 텍스트 레이어 O → 텍스트
                          └─ 스캔/이미지/HWP → OCR(Stage A) 또는 이미지
        → ContentPart[] (text|image, 프로바이더 중립)
        → pipeline: Stage B(self-consistency 추출) → Stage C(검증·신뢰도·게이트 재추출)
        → Pydantic 검증 → JSON(+필드별 신뢰도/근거)
```

- 로더: `src/docs_reader/loaders/` (pdf/office/image/hwp) + `convert.py`(soffice)
- OCR Stage A: `src/docs_reader/ocr/` (rapidocr/docling 어댑터, 없으면 비전 폴백)
- 프로바이더: `src/docs_reader/providers/` (openai_compat/gemini/claude/mock)
- 파이프라인: `src/docs_reader/pipeline/` (extract/verify/confidence)

## 개발/테스트

```bash
pip install -e ".[dev]"
python tools/make_samples.py     # samples/ 데모 문서 생성
pytest -q
```
