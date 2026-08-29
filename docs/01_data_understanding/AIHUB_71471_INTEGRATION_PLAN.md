# AI Hub 71471 통합 계획

## 목적

`71471`은 ASF 질병 데이터가 아니라 발정행동 데이터입니다. 그래서 이 데이터는 ASF 탐지 성능을 직접 증명하는 용도가 아니라, 돼지 행동 변화와 활동량 feature를 보강할 수 있는지 확인하는 후보 데이터로 둡니다.

## 현재 결정

| 항목 | 판단 |
| --- | --- |
| 프로젝트 내 우선순위 | 4순위 |
| 사용 목적 | 622 행동량 트랙 보강 후보 검토 |
| 메인 학습 직접 투입 | 보류 |
| 먼저 받을 파일 | 메타데이터, 라벨 파일 |
| 나중에 받을 파일 | 대용량 원천 이미지/영상 |

## 실행 순서

1. AI Hub에서 71471 데이터 이용 신청/승인을 확인합니다.
2. API 키를 환경변수로 설정합니다.
3. 파일 목록을 저장합니다.
4. 돼지 관련 메타데이터와 라벨 파일만 먼저 다운로드합니다.
5. 라벨 스키마를 확인합니다.
6. `622` 행동량 feature와 공통 컬럼으로 맞출 수 있는지 판단합니다.

## 실행 명령

```bash
cd /Users/bangjiwon/dev/pigproject
source .venv/bin/activate
export AIHUB_API_KEY="발급받은_키"
export AIHUBSHELL_BIN="/Users/bangjiwon/dev/pigproject/bin/aihubshell"

pig-aihub recommended --dataset-key 71471
pig-aihub files --dataset-key 71471 > artifacts/aihub_71471_file_tree.txt
```

`.env`에 `AIHUB_API_KEY`를 넣어둔 경우에는 아래 스크립트가 자동으로 `.env`를 읽습니다.

파일 목록에서 돼지 라벨 또는 메타데이터에 해당하는 `filekey`를 확인한 뒤 다음처럼 받습니다.

```bash
pig-aihub download \
  --dataset-key 71471 \
  --file-key "확인한_filekey" \
  --output-dir data/raw/aihub/71471
```

현재 확인된 1차 다운로드 대상은 다음입니다.

| 파일 | 크기 | filekey | 이유 |
| --- | ---: | --- | --- |
| `01.메타데이터.zip` | 311 B | `511265` | 전체 데이터 설명 확인 |
| `TL_3.돼지_01.이미지_002.keypoints.zip` | 28 MB | `511411` | 돼지 training keypoints 라벨 |
| `VL_3.돼지_01.이미지_002.keypoints.zip` | 4 MB | `511459` | 돼지 validation keypoints 라벨 |

한 번에 받으려면 다음 스크립트를 사용합니다.

```bash
bash scripts/download_aihub_71471_labels.sh
```

## 받을 때의 원칙

- 원천 이미지/영상은 크기가 클 수 있으므로 처음부터 받지 않습니다.
- 먼저 라벨과 메타데이터만 받아서 시간축, 개체 ID, 돈방/카메라 ID, 행동 라벨이 있는지 확인합니다.
- 돼지 데이터가 소 데이터와 같은 압축 파일에 섞여 있으면, 다운로드 후 돼지 파일만 분리 가능한지 확인합니다.

## 통합 가능성 판단 기준

| 확인 항목 | 통합 가능 판단 |
| --- | --- |
| `animal_id` 또는 개체 ID | 개체별 행동 변화 추적 가능 |
| `datetime` 또는 frame timestamp | 10분 단위 시계열 변환 가능 |
| camera/pen/chamber ID | 돈방 단위 집계 가능 |
| behavior class | standing/lying/mounting/resting 등 행동량 feature 후보 생성 가능 |
| bbox/keypoint | 622 activity feature와 유사한 이동량/자세 feature 생성 가능 |

## 현재 프로젝트 반영 위치

- 데이터셋 등록: `config/aihub_datasets.json`
- 다운로드 가이드: `../01_data_understanding/AIHUB_API_ACTION_GUIDE.md`
- 전체 외부 데이터 목록: `data/raw/EXTERNAL_DATA_DOWNLOADS.md`

71471 라벨 스키마가 확인되면 다음 단계는 `pig-normalize`에 71471 전용 loader 또는 alias mapping을 추가하는 것입니다.
