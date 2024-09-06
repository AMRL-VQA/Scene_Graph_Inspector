# Scebe Graph Inspector GUI

장면 그래프 검수용 GUI 프로그램 입니다.

🔥폴더를 열 떄, 반드시 ```images``` 폴더가 아닌 ```Dataset``` 폴더를 열어주세요.

***-2024-08-30일 업데이트-***

① 이미지 상의 화살표 선을 클릭 시, 해당 Triple의 수정 화면이 뜨는 기능 추가. [Request By 이성국]

② 전체 체크박스 일괄 체크/해제 버튼 추가. [Request By 이찬빈]

***-2024-09-01일 업데이트-***

① Triple 수정 화면에서 ```Enter```키 입력 시, 확인 버튼 눌림 기능 추가 [Request By 최지윤, 이준아]

② Triple 수정 화면에 화살표 방향 전환 버튼 추가 [Request By 양승현]

③ 전체 체크박스 일괄 체크/해제 단축키 ```CTRL + A``` 추가 [Added By 박균]

④ 중복 Triple 알림 화면에서 수정 전의 Triple 삭제 버튼 추가 [Request By 김세헌]

⑤ Triple 수정 화면이 여러 개인 경우, 창을 닫으면 메인 창이 아닌 다른 Triple 수정 화면에 포커스가 가도록 변경

***-2024-09-03일 업데이트-***

① 일부 속성값(예: Flying, Landed, One-story building, etc.)을 바운딩박스 좌측 상단에 표시

***-2024-09-06일 업데이트-***

① 새로운 Triple 추가 기능 메뉴와 버튼을 추가하고 단축키 ```CTRL + N```에 할당 [Request By 박균]

② Tripel 추가/수정 창에서 ```ESC``` 키를 눌르면 화면에서 나가지는 기능 추가 [Request By 최지윤]


## Setup

1. Clone 후, 해당 폴더로 이동
```
git clone https://github.com/AMRL-VQA/Scene_Graph_Inspector.git
cd Scene_Graph_Inspector
```

2. 실행에 필요한 패키지 설치
```
pip install -r requirements.txt
```

3. 이미지 데이터를 [다운로드](https://drive.google.com/drive/folders/1H0NwjLpS2OHq-pLTCbIQwOfdDeWkP4OZ?usp=sharing)한 뒤, `Dataset/images` 폴더 안에 압축 풀기

- 예시

```
📦Dataset
 ┣ 📂images
 ┃ ┣ 📜000001.jpg
 ┃ ┣ 📜000002.jpg
 ┃ ┣    ⁞
 ┣ 📂json
 ┃ ┗ 📜VQA_data_with_scene_graph(000001~003000)-2024-08-28_04-51-02.json
 ┃ ┗ 📜VQA_data_with_scene_graph(000001~003000)-2024-08-28_06-52-55.json
 ┃ ┣    ⁞
 ┗ 📜data.yaml
```

## Run
1. `scene_graph_inspector.py`로 프로그램 실행

2. 우측 상단의 `File` → `Open Folder` 또는 `CTRL + O`을 눌러서 폴더 선택 창을 연 뒤, `Dataset` 폴더를 선택하여 연다.

3. 장면 그래프를 검수 한 뒤, 저장을 위해 `File` → `Save to JSON` 또는 `CTRL + S`을 눌러서 저장한다.

4. 이미지 위의 그려진 선들의 색상이 잘 안보이면, `Random Color` → `Get Random Color` 또는 `CTRL + R`을 눌러서 색상을 변경한다.

## 기타 사항

- 이미지 제작에 사용한 프로그램: ARMA3의 [Eden Editor](https://community.bistudio.com/wiki/Category:Eden_Editor)
  
<img
  src="https://i.namu.wiki/i/EmIh3Am-eSOoMK_Dkw002A5GboINsi5bS1F6Cpy4vGwtqofuMj7_-QkMiqJuVfXoK2DvFXqE1ABJd2wkX3CeKw.webp"
  width="388.5"
  height="550"
/>
