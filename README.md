# Scebe Graph Inspector GUI

장면 그래프 검수용 GUI 프로그램 입니다.

## Setup

1. Clone 후, 해당 폴더로 이동
```

```

2. 실행에 필요한 패키지 설치
```
pip install -r requirements.txt
```

3. 이미지 데이터를 [다운로드]()한 뒤, `Dataset/images` 폴더 안에 압축 풀기

- 예시

```
📦Dataset
 ┣ 📂images
 ┃ ┣ 📜000001.jpg
 ┃ ┣ 📜000002.jpg
 ┃ ┣    ⁞
 ┣ 📂json
 ┃ ┗ 📜VQA_data_with_scene_graph-changed-2024-08-27_17-11-40.json
 ┗ 📜data.yaml
```

## Run
1. `scene_graph_inspector.py`로 프로그램 실행

2. 우측 상단의 `File` → `Open Folder` 또는 `CTRL + O`을 눌러서 폴더 선택 창을 연 뒤, `Dataset` 폴더를 선택하여 연다.

3. 장면 그래프를 검수 한 뒤, 저장을 위해 `File` → `Save to JSON` 또는 `CTRL + S`을 눌러서 저장한다.

4. 이미지 위의 그려진 선들의 색상이 잘 안보이면, `Random Color` → `Get Random Color` 또는 `CTRL + R`을 눌러서 색상을 변경한다.
