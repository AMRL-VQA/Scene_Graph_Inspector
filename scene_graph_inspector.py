import copy
from datetime import datetime
import glob
import json
import math
import os
import threading
import queue
import yaml
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from tkinter.ttk import *
from ttkthemes import ThemedTk
from PIL import Image, ImageTk, ImageDraw, ImageFont


class ImageLabelingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Labeling App")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Edit Triple 병렬 처리를 위한 Queue 생성
        self.task_queue = queue.Queue()
        self.root.after(100, self.process_queue)

        # PanedWindow 생성
        self.paned_window = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, sashrelief=tk.GROOVE
        )
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # 좌측 패널: 이미지 리스트
        self.left_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.left_frame, minsize=170)  # 최소 크기 설정

        self.left_scrollbar = ttk.Scrollbar(self.left_frame)
        self.left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.image_listbox = tk.Listbox(
            self.left_frame, yscrollcommand=self.left_scrollbar.set
        )
        self.image_listbox.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True
        )  # fill=tk.BOTH와 expand=True 추가
        self.image_listbox.bind("<<ListboxSelect>>", self.on_image_select)

        self.left_scrollbar.config(command=self.image_listbox.yview)

        # 중앙 패널: 이미지 표시
        self.center_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.center_frame, width=1500)  # 초기 너비 설정

        # 중앙 패널 상단에 프레임 추가
        self.top_frame = tk.Frame(self.center_frame)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        # 이전 이미지로 이동하는 버튼
        self.prev_button = ttk.Button(
            self.top_frame,
            text="Previous",
            command=self.show_previous_image,
            width=10,
            padding=(20, 30),
        )
        self.prev_button.pack(side=tk.LEFT)

        # 현재 이미지 이름을 표시할 라벨
        self.image_name_label = tk.Label(
            self.top_frame, text="Image Name", font=("Arial", 24)
        )
        self.image_name_label.pack(side=tk.LEFT, expand=True)

        # 다음 이미지로 이동하는 버튼
        self.next_button = ttk.Button(
            self.top_frame,
            text="Next",
            command=self.show_next_image,
            width=10,
            padding=(20, 30),
        )
        self.next_button.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(self.center_frame)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # 우측 패널: 장면 그래프
        self.right_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.right_frame, minsize=450)  # 최소 크기 설정

        # 우측 패널에 스크롤바 추가
        self.right_scrollbar = ttk.Scrollbar(self.right_frame)
        self.right_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 스크롤 가능한 캔버스 생성
        self.scroll_canvas = tk.Canvas(
            self.right_frame, yscrollcommand=self.right_scrollbar.set
        )
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 스크롤바와 캔버스 연결
        self.right_scrollbar.config(command=self.scroll_canvas.yview)

        # 캔버스 내부에 프레임 생성
        self.notebook_frame = tk.Frame(self.scroll_canvas)
        self.scroll_canvas.create_window(
            (0, 0), window=self.notebook_frame, anchor="nw"
        )

        # 프레임 내부에 노트북 추가
        self.notebook = ttk.Notebook(self.notebook_frame, style="TNotebook.Tab")
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.last_selected_tab = None

        # 캔버스 크기 조정 이벤트 바인딩
        self.notebook_frame.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.configure(
                scrollregion=self.scroll_canvas.bbox("all")
            ),
        )

        # 탭 변경 이벤트 바인딩
        self.notebook.bind(
            "<<NotebookTabChanged>>",
            lambda event: self.uncheck_relation_triples_except_current_tab(),
        )

        self.predicate_tabs = {}
        self.predicate_checkbuttons = {}

        self.predicates = [
            "to the left of",
            "to the right of",
            "above",
            "below",
            "in front of",
            "behind",
            "inside",
            "located in",
            "holding",
            "carrying",
            "riding"
        ]

        self.relation_triples = (
            []
        )  # This should be populated with the actual relation triples

        self.checkbox_vars = {}

        # 장면그래프 정보 초기화 여부
        self.relation_triple_info_initialized = False

        # 메뉴
        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)

        self.file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(
            label="Open Folder [CTRL + O]", command=self.open_folder
        )
        self.file_menu.add_command(
            label="Save to JSON [CTRL + S]", command=self.save_to_json
        )

        # Ctrl + S 키 조합을 save_to_json 함수에 바인딩
        self.root.bind("<Control-s>", lambda event: self.save_to_json())
        # Ctrl + r 키 조합을 class_and_predicate_random_color 함수에 바인딩
        self.root.bind(
            "<Control-r>", lambda event: self.class_and_predicate_random_color()
        )
        # Ctrl + O 키 조합을 open_folder 함수에 바인딩
        self.root.bind("<Control-o>", lambda event: self.open_folder())
        # Ctrl + A 키 조합을 toggle_all_checkbuttons_with_shortcut 함수에 바인딩
        self.root.bind("<Control-a>", lambda event: self.toggle_all_checkbuttons_with_shortcut())

        self.random_color_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Random Color", menu=self.random_color_menu)
        self.random_color_menu.add_command(
            label="Get Random Color [CTRL + R]",
            command=self.class_and_predicate_random_color,
        )

        self.folder_path = ""
        self.Class = []
        self.image_files = []
        self.label_files = {}
        self.current_image = None

        # 색상 매핑
        self.class_colors = {}
        self.predicate_colors = {}

        # 전체 체크/해제 체크버튼 변수
        self.checkbox_vars = {}

        # 열린 edit_dialog 창들을 추적하기 위한 리스트
        self.open_dialogs = []

    def process_queue(self):
        while not self.task_queue.empty():
            task = self.task_queue.get()
            task()
        self.root.after(100, self.process_queue)

    def on_closing(self):
        # json 폴더안에 저장되어 있는 파일들을 확인하여 가장 최근 파일의 시간이 현재 시간과 1분 이상 차이가 나는 경우
        # 사용자에게 저장 여부를 묻는 메시지 창을 띄움
        tmp_json_path_list = glob.glob(os.path.join(self.folder_path, "json", "*.json"))
        tmp_json_path_list.sort(key=lambda x: os.path.getmtime(x))
        if tmp_json_path_list:
            if (
                datetime.now().timestamp() - os.path.getmtime(tmp_json_path_list[-1])
                > 60
            ):
                # 저장하고 종료, 저장하지 않고 종료, 취소 중 하나 선택
                answer = messagebox.askyesnocancel(
                    "종료",
                    "최종 변경 사항을 저장하고 종료 하시겠습니까?",
                    default=messagebox.CANCEL,
                )
                if answer is None:
                    return
                elif answer:
                    self.save_to_json()
        self.root.destroy()

    def save_to_json(self):
        # self.vqa_data를 deepcopy하여 self.changed_vqa_data 생성
        self.changed_vqa_data = copy.deepcopy(self.vqa_data)

        # 현재 날짜와 시간가 이미지 파일 범위를 가져와 파일 이름 생성
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        first_image_name = os.path.basename(self.image_files[0]).split(".")[0]
        last_image_name = os.path.basename(self.image_files[-1]).split(".")[0]
        file_name = os.path.join(
            self.folder_path,
            "json",
            f"VQA_data_with_scene_graph({first_image_name}~{last_image_name})-{current_time}.json",
        )

        # self.changed_vqa_data를 JSON 파일로 저장
        with open(file_name, "w", encoding="utf-8") as json_file:
            # 각 이미지별 relation triple들에서 중복되는 triple(딕셔너리) 제거
            for item in self.changed_vqa_data:
                tmp_list: list[dict] = item["scene_graph"]["triples"]
                item["scene_graph"]["triples"] = [
                    dict(t) for t in {tuple(d.items()) for d in tmp_list}
                ]

            json.dump(self.changed_vqa_data, json_file, ensure_ascii=False, indent=4)

        # 저장이 완료되었음을 알리는 메시지 창 띄우기
        # 상대 주소로 파일 이름을 표시
        messagebox.showinfo(
            "저장 완료",
            f"{os.path.relpath(file_name, self.folder_path)} 파일 저장 완료",
        )

    def show_previous_image(self):
        current_index = self.image_files.index(self.current_image)
        if current_index > 0:
            self.current_image = self.image_files[current_index - 1]
            self.image_listbox.selection_clear(0, tk.END)  # 기존 선택을 모두 해제
            self.image_listbox.selection_set(current_index - 1)  # 주어진 인덱스를 선택
            self.image_listbox.activate(
                current_index - 1
            )  # 선택된 항목으로 포커스를 이동

            self.relation_triple_info_initialized = False
            self.last_selected_tab = None
            self.display_image()

    def show_next_image(self):
        current_index = self.image_files.index(self.current_image)
        if current_index < len(self.image_files) - 1:
            self.current_image = self.image_files[current_index + 1]
            self.image_listbox.selection_clear(0, tk.END)  # 기존 선택을 모두 해제
            self.image_listbox.selection_set(current_index + 1)  # 주어진 인덱스를 선택
            self.image_listbox.activate(current_index + 1)

            self.relation_triple_info_initialized = False
            self.last_selected_tab = None
            self.display_image()

    def open_folder(self):
        self.folder_path = filedialog.askdirectory()
        if not self.folder_path:
            return

        self.image_files = []
        self.image_listbox.delete(0, tk.END)

        # 하위 폴더의 이미지도 검색하도록 수정
        for idx, img_file in enumerate(
            glob.glob(os.path.join(self.folder_path, "**", "*.jpg"), recursive=True)
        ):
            self.image_files.append(img_file)
            self.image_listbox.insert(
                tk.END, f"{idx + 1}. {os.path.relpath(img_file, self.folder_path)}"
            )  # 이미지 리스트에 번호 추가

        # data.yaml 파일 읽기
        yaml_path = os.path.join(self.folder_path, "data.yaml")
        if os.path.exists(yaml_path):
            with open(yaml_path, "r") as file:
                data = yaml.safe_load(file)
                self.Class = data.get("names", [])
                # 클래스별 랜덤 색상 매핑
                self.class_colors = {cls: self.get_random_color() for cls in self.Class}
                self.predicate_colors = {
                    predicate: self.get_random_color() for predicate in self.predicates
                }
                # print(self.class_colors)
        else:
            self.Class = []

        # VQA_data_with_scene_graph.json 파일 읽기
        json_path_list = glob.glob(os.path.join(self.folder_path, "json", "*.json"))
        json_path_list.sort(
            key=lambda x: os.path.getmtime(x)
        )  # 날짜와 시간이 포함된 파일명을 기준으로 정렬
        json_path = json_path_list[-1]  # 가장 최근 파일 선택
        print(json_path)
        if os.path.exists(json_path):
            with open(json_path, "r") as file:
                self.vqa_data = json.load(file)
        else:
            self.vqa_data = {}

    def display_image(self):
        if not self.current_image:
            return

        image_path = self.current_image
        image = Image.open(image_path)

        self.image_name_label.config(text=os.path.basename(image_path))

        # 중앙 패널의 너비에 맞춰 이미지 리사이즈
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        aspect_ratio = image.height / image.width
        new_width = canvas_width
        new_height = int(new_width * aspect_ratio)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 이미지의 현재 크기와 위치 저장
        self.image_x = (canvas_width - new_width) // 2
        self.image_y = (canvas_height - new_height) // 2
        self.current_image_width = new_width
        self.current_image_height = new_height

        # 레이블 정보 읽기
        image_name = os.path.basename(image_path)
        objects = []
        relation_triples = []
        for item in self.vqa_data:
            if item["image"]["image_name"] == image_name:
                objects = item["scene_graph"]["objects"]
                relation_triples = item["scene_graph"]["triples"]
                break
        self.objects = objects
        self.object_ids = [obj["object_id"] for obj in self.objects]
        self.objects_ids_with_class = [
            f"{obj['class']}: {obj['object_id']}" for obj in self.objects
        ]
        self.relation_triples = relation_triples
        # print(f"Objects: {self.objects}")
        # print(f"Relation triples: {self.relation_triples}")

        # Relation Triple 표시
        if not self.relation_triple_info_initialized:
            self.display_relation_triples()
            self.relation_triple_info_initialized = True
            # print("Relation triple info initialized")  # 디버깅 출력

        # Relation Triple 그리기
        self.draw_relation_triple(image)

        self.canvas.create_image(
            canvas_width // 2, canvas_height // 2, anchor=tk.CENTER, image=self.tk_image
        )

        self.canvas.bind("<Button-1>", self.on_image_click)

    def on_image_click(self, event):
        # 클릭된 지점의 좌표 얻기
        x = event.x
        y = event.y

        clicked_triple = []

        # 클릭된 지점이 이미지 내부에 있는지 확인
        if (
            self.image_x <= x <= self.image_x + self.current_image_width
            and self.image_y <= y <= self.image_y + self.current_image_height
        ):
            # 이미지 상의 좌표로 변환
            image_x = x - self.image_x
            image_y = y - self.image_y
            image_x /= self.current_image_width
            image_y /= self.current_image_height

            # 현재 선택된 탭의 이름을 가져옴
            current_predicate = self.notebook.tab(self.notebook.select(), "text")

            # Subject와 Bounding의 중심 지점을 이은 선분의 방정식을 이용하여 클릭한 지점이 선분 위에 있는지 확인
            for triple in self.relation_triples:
                if triple["predicate"] != current_predicate:
                    continue
                object = None
                subject = None
                for obj in self.objects:
                    if obj["object_id"] == triple["object_id"]:
                        object = obj
                    elif obj["object_id"] == triple["subject_id"]:
                        subject = obj
                    if object and subject:
                        break

                subject_x_center, subject_y_center, subject_width, subject_height = (
                    subject["bounding_box"]
                )
                object_x_center, object_y_center, object_width, object_height = object[
                    "bounding_box"
                ]

                # 선분의 방정식: y = ax + b
                # Divide by Zero 예방
                if object_x_center  == subject_x_center:
                    a = (object_y_center - subject_y_center) / sys.float_info.epsilon
                    b = subject_y_center - a * subject_x_center
                else:
                    a = (object_y_center - subject_y_center) / (
                        object_x_center - subject_x_center
                    )
                    b = subject_y_center - a * subject_x_center

                minimum_margin = 0.005

                # 클릭한 지점이 선분 위에 있는지 확인
                if (
                    min(object_x_center, subject_x_center) - minimum_margin
                    <= image_x
                    <= max(object_x_center, subject_x_center) + minimum_margin
                    and min(object_y_center, subject_y_center) - minimum_margin
                    <= image_y
                    <= max(object_y_center, subject_y_center) + minimum_margin
                ):
                    # print(f"Triple: {triple}")
                    # 선분과 점 사이의 거리가 0.005 이하인 경우에만 클릭한 것으로 간주
                    d = abs(a * image_x - image_y + b) / math.sqrt(a ** 2 + 1)
                    if d <= 0.005:
                        clicked_triple.append(triple)

        if clicked_triple:
            # edit_triple을 Queue에 추가하여 메인 스레드에서 실행되도록 함
            for triple in clicked_triple:
                # print(f"triple: {triple}")
                self.root.after_idle(
                    self.edit_triple,
                    (
                        triple["subject_id"],
                        triple["predicate"],
                        triple["object_id"],
                    ),
                )

        # print(f"Clicked at ({image_x}, {image_y})")

    def draw_relation_triple(self, image):
        draw = ImageDraw.Draw(image)

        for triple, var in self.predicate_checkbuttons.items():
            if var.get():
                triple_dict = {
                    "subject_id": triple[0],
                    "predicate": triple[1],
                    "object_id": triple[2],
                }

                # Draw the bounding boxes of the subject and object
                subject = next(
                    obj
                    for obj in self.objects
                    if obj["object_id"] == triple_dict["subject_id"]
                )
                object = next(
                    obj
                    for obj in self.objects
                    if obj["object_id"] == triple_dict["object_id"]
                )

                subject_x_center, subject_y_center, subject_width, subject_height = (
                    subject["bounding_box"]
                )
                subject_x1 = (subject_x_center - subject_width / 2) * image.width
                subject_y1 = (subject_y_center - subject_height / 2) * image.height
                subject_x2 = (subject_x_center + subject_width / 2) * image.width
                subject_y2 = (subject_y_center + subject_height / 2) * image.height
                subject_bounding_box = [subject_x1, subject_y1, subject_x2, subject_y2]

                object_x_center, object_y_center, object_width, object_height = object[
                    "bounding_box"
                ]
                object_x1 = (object_x_center - object_width / 2) * image.width
                object_y1 = (object_y_center - object_height / 2) * image.height
                object_x2 = (object_x_center + object_width / 2) * image.width
                object_y2 = (object_y_center + object_height / 2) * image.height
                object_bounding_box = [object_x1, object_y1, object_x2, object_y2]

                # Draw the bounding boxes
                draw.rectangle(
                    subject_bounding_box,
                    outline=self.class_colors[subject["class"]],
                    width=3,
                )
                draw.rectangle(
                    object_bounding_box,
                    outline=self.class_colors[object["class"]],
                    width=2,
                )

                abs_subject_x_center = subject_x_center * image.width
                abs_subject_y_center = subject_y_center * image.height
                abs_object_x_center = object_x_center * image.width
                abs_object_y_center = object_y_center * image.height

                draw.line(
                    (
                        abs_subject_x_center,
                        abs_subject_y_center,
                        abs_object_x_center,
                        abs_object_y_center,
                    ),
                    fill=self.predicate_colors[triple_dict["predicate"]],
                    width=3,
                )

                arrow_angle = 30
                angle = math.atan2(
                    abs_object_y_center - abs_subject_y_center,
                    abs_object_x_center - abs_subject_x_center,
                )
                angle1 = angle + math.radians(arrow_angle)
                angle2 = angle + math.radians(-arrow_angle)
                arrow_length = 20

                draw.line(
                    (
                        abs_object_x_center - arrow_length * math.cos(angle1),
                        abs_object_y_center - arrow_length * math.sin(angle1),
                        abs_object_x_center,
                        abs_object_y_center,
                    ),
                    fill=self.predicate_colors[triple_dict["predicate"]],
                    width=3,
                )
                draw.line(
                    (
                        abs_object_x_center - arrow_length * math.cos(angle2),
                        abs_object_y_center - arrow_length * math.sin(angle2),
                        abs_object_x_center,
                        abs_object_y_center,
                    ),
                    fill=self.predicate_colors[triple_dict["predicate"]],
                    width=3,
                )

        self.tk_image = ImageTk.PhotoImage(image)

    def display_relation_triples(self):
        # print("display_relation_triples called")  # 디버깅 출력

        # 기존의 모든 탭 제거
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        self.predicate_tabs.clear()
        self.predicate_checkbuttons.clear()
        self.checkbox_vars.clear()

        for predicate in self.predicates:
            # print(f"Processing predicate: {predicate}")  # 디버깅 출력
            triples = [
                triple
                for triple in self.relation_triples
                if triple["predicate"] == predicate
            ]
            # print(triples)
            if triples:
                frame = ttk.Frame(self.notebook)
                self.notebook.add(frame, text=predicate)
                self.predicate_tabs[predicate] = frame

                row = 0  # 행 번호 초기화
                select_all_var = tk.BooleanVar()
                select_all_var.set(True)
                self.checkbox_vars[predicate] = select_all_var
                select_all_checkbutton = ttk.Checkbutton(
                    frame,
                    text="전체 체크/해제",
                    variable=select_all_var,
                    command=lambda p=predicate, v=self.checkbox_vars[predicate] : self.toggle_all_checkbuttons(p,v)
                )
                select_all_checkbutton.grid(row=row, column=0, sticky="w")
                row += 1

                for triple in triples:
                    var = tk.BooleanVar()
                    var.set(True)
                    triple_key = (
                        triple["subject_id"],
                        triple["predicate"],
                        triple["object_id"],
                    )

                    # 삭제 버튼 생성
                    delete_button = ttk.Button(
                        frame,
                        text="삭제",
                        command=lambda tk=triple_key: self.delete_triple(tk),
                        name=f"{triple_key[0]}-{triple_key[1]}-{triple_key[2]}-delete",
                    )
                    delete_button.grid(
                        row=row, column=0, sticky="w"
                    )  # 첫 번째 열에 배치

                    # 체크버튼 생성
                    checkbutton = ttk.Checkbutton(
                        frame,
                        text=f"{triple['subject_id']} - {triple['predicate']} - {triple['object_id']}",
                        variable=var,
                        command=self.display_image,
                    )
                    checkbutton.grid(row=row, column=1, sticky="w")  # 두 번째 열에 배치

                    # predicate 수정 버튼 생성
                    edit_button = ttk.Button(
                        frame,
                        text="수정",
                        command=lambda tk=triple_key: self.edit_triple(tk),
                        name=f"{triple_key[0]}-{triple_key[1]}-{triple_key[2]}-edit",
                    )
                    edit_button.grid(row=row, column=2, sticky="w")  # 세 번째 열에 배치

                    self.predicate_checkbuttons[triple_key] = var
                    row += 1  # 다음 행으로 이동

        if self.last_selected_tab is not None:
            try:
                self.notebook.select(self.last_selected_tab)
            except:
                pass
        else:
            # 첫번쨰 탭 선택 및 포커스 후 짥은 시간 대기
            self.notebook.select(0)
            self.root.after(100, lambda: self.notebook.focus_set())

    def toggle_all_checkbuttons(self, predicate, var):
        for triple, checkbutton in self.predicate_checkbuttons.items():
            if triple[1] == predicate:
                checkbutton.set(var.get())
        self.display_image()

    def toggle_all_checkbuttons_with_shortcut(self):
        current_predicate = self.notebook.tab(self.notebook.select(), "text")
        # print(f"Current predicate: {current_predicate}")
        # print(f"Initizlized: {self.relation_triple_info_initialized}")
        var = self.checkbox_vars[current_predicate]
        var.set(not var.get())
        self.checkbox_vars[current_predicate] = var
        # print(var.get())
        # self.notebook.unbind("<<NotebookTabChanged>>")
        self.toggle_all_checkbuttons(current_predicate, var)

    def delete_triple(self, triple_key):
        # UI에서 삭제
        for widget in self.predicate_tabs[triple_key[1]].winfo_children():
            if (
                isinstance(widget, ttk.Checkbutton)
                and widget["text"]
                == f"{triple_key[0]} - {triple_key[1]} - {triple_key[2]}"
            ):
                widget.grid_forget()
            elif (
                isinstance(widget, ttk.Button)
                and f"{triple_key[0]}-{triple_key[1]}-{triple_key[2]}"
                in widget.winfo_name()
            ):
                widget.grid_forget()

        # self.predicate_checkbuttons에서 삭제
        self.predicate_checkbuttons.pop(triple_key)

        # self.vqa_data에서 삭제
        for item in self.vqa_data:
            if item["image"]["image_name"] == os.path.basename(self.current_image):
                item["scene_graph"]["triples"] = [
                    triple
                    for triple in item["scene_graph"]["triples"]
                    if not (
                        triple["subject_id"] == triple_key[0]
                        and triple["predicate"] == triple_key[1]
                        and triple["object_id"] == triple_key[2]
                    )
                ]
                break

        # 이미지 다시 그리기
        self.display_image()

    def edit_triple(self, triple_key):
        # 수정 Dialog 생성
        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title("Triple 수정")
        edit_dialog.focus_set()

        # 열린 Dialog 창을 리스트에 추가
        self.open_dialogs.append(edit_dialog)

        # 수정할 subject_id, predicate, object_id 입력 칸 생성
        # 각각의 입력 칸은 기본값으로 기존 값이 들어가도록 함
        # Predicate의 경우 self.predicates에 있는 값 중 하나만 입력 가능하도록 함
        # subject_id, object_id는 해당 이미지의 object_list에 있는 object_id 중 하나만 입력 가능하도록 함
        subject_id_var = tk.StringVar()
        for obj in self.objects:
            if obj["object_id"] == triple_key[0]:
                subject_id_var.set(f"{obj['class']}: {obj['object_id']}")
                break
        subject_id_label = tk.Label(edit_dialog, text="Subject ID:")
        subject_id_label.grid(row=0, column=0)
        subject_id_entry = ttk.Combobox(
            edit_dialog,
            textvariable=subject_id_var,
            values=self.objects_ids_with_class,
            width=30,
        )
        subject_id_entry.grid(row=0, column=1)

        predicate_var = tk.StringVar()
        predicate_var.set(triple_key[1])
        predicate_label = tk.Label(edit_dialog, text="Predicate:")
        predicate_label.grid(row=1, column=0)
        predicate_entry = ttk.Combobox(
            edit_dialog, textvariable=predicate_var, values=self.predicates, width=30
        )
        predicate_entry.grid(row=1, column=1)
        object_id_var = tk.StringVar()
        for obj in self.objects:
            if obj["object_id"] == triple_key[2]:
                object_id_var.set(f"{obj['class']}: {obj['object_id']}")
                break
        object_id_label = tk.Label(edit_dialog, text="Object ID:")
        object_id_label.grid(row=2, column=0)
        object_id_entry = ttk.Combobox(
            edit_dialog,
            textvariable=object_id_var,
            values=self.objects_ids_with_class,
            width=30,
        )
        object_id_entry.grid(row=2, column=1)

        # 수정된 값이 이미지에서 어떻게 보일지 Dialog 상에 이미지로 표시
        image = Image.open(self.current_image)
        draw = ImageDraw.Draw(image)

        # 이미지 보여주는 캔버스 생성 후 Dialog에 추가. 이때 이미지는 1280x720 크기로 resize
        canvas = tk.Canvas(edit_dialog, width=1280, height=720)
        canvas.grid(row=3, column=0, columnspan=4)
        tk_image = ImageTk.PhotoImage(image.resize((1280, 720)))
        canvas.create_image(640, 360, image=tk_image)

        # 이미지에 subject_id, object_id에 해당하는 bounding box 그리기
        for obj in self.objects:
            if obj["object_id"] == int(subject_id_var.get().split(": ")[1]):
                subject_x_center, subject_y_center, subject_width, subject_height = obj[
                    "bounding_box"
                ]
                subject_x1 = (subject_x_center - subject_width / 2) * image.width
                subject_y1 = (subject_y_center - subject_height / 2) * image.height
                subject_x2 = (subject_x_center + subject_width / 2) * image.width
                subject_y2 = (subject_y_center + subject_height / 2) * image.height
                draw.rectangle(
                    (subject_x1, subject_y1, subject_x2, subject_y2),
                    outline=self.class_colors[obj["class"]],
                    width=3,
                )
            if obj["object_id"] == int(object_id_var.get().split(": ")[1]):
                object_x_center, object_y_center, object_width, object_height = obj[
                    "bounding_box"
                ]
                object_x1 = (object_x_center - object_width / 2) * image.width
                object_y1 = (object_y_center - object_height / 2) * image.height
                object_x2 = (object_x_center + object_width / 2) * image.width
                object_y2 = (object_y_center + object_height / 2) * image.height
                draw.rectangle(
                    (object_x1, object_y1, object_x2, object_y2),
                    outline=self.class_colors[obj["class"]],
                    width=3,
                )

        abs_subject_x_center = subject_x_center * image.width
        abs_subject_y_center = subject_y_center * image.height
        abs_object_x_center = object_x_center * image.width
        abs_object_y_center = object_y_center * image.height

        draw.line(
            (
                abs_subject_x_center,
                abs_subject_y_center,
                abs_object_x_center,
                abs_object_y_center,
            ),
            fill=self.predicate_colors[predicate_var.get()],
            width=3,
        )

        arrow_angle = 30
        angle = math.atan2(
            abs_object_y_center - abs_subject_y_center,
            abs_object_x_center - abs_subject_x_center,
        )
        angle1 = angle + math.radians(arrow_angle)
        angle2 = angle + math.radians(-arrow_angle)
        arrow_length = 20

        draw.line(
            (
                abs_object_x_center - arrow_length * math.cos(angle1),
                abs_object_y_center - arrow_length * math.sin(angle1),
                abs_object_x_center,
                abs_object_y_center,
            ),
            fill=self.predicate_colors[predicate_var.get()],
            width=3,
        )
        draw.line(
            (
                abs_object_x_center - arrow_length * math.cos(angle2),
                abs_object_y_center - arrow_length * math.sin(angle2),
                abs_object_x_center,
                abs_object_y_center,
            ),
            fill=self.predicate_colors[predicate_var.get()],
            width=3,
        )

        tk_image = ImageTk.PhotoImage(image.resize((1280, 720)))
        canvas.create_image(640, 360, image=tk_image)

        # 값이 바뀔 때마다 이미지 다시 그리기
        def update_image(var_name, index, operation):
            image = Image.open(self.current_image)
            draw = ImageDraw.Draw(image)

            for obj in self.objects:
                if obj["object_id"] == int(subject_id_var.get().split(": ")[1]):
                    (
                        subject_x_center,
                        subject_y_center,
                        subject_width,
                        subject_height,
                    ) = obj["bounding_box"]
                    subject_x1 = (subject_x_center - subject_width / 2) * image.width
                    subject_y1 = (subject_y_center - subject_height / 2) * image.height
                    subject_x2 = (subject_x_center + subject_width / 2) * image.width
                    subject_y2 = (subject_y_center + subject_height / 2) * image.height
                    draw.rectangle(
                        (subject_x1, subject_y1, subject_x2, subject_y2),
                        outline=self.class_colors[obj["class"]],
                        width=3,
                    )
                if obj["object_id"] == int(object_id_var.get().split(": ")[1]):
                    object_x_center, object_y_center, object_width, object_height = obj[
                        "bounding_box"
                    ]
                    object_x1 = (object_x_center - object_width / 2) * image.width
                    object_y1 = (object_y_center - object_height / 2) * image.height
                    object_x2 = (object_x_center + object_width / 2) * image.width
                    object_y2 = (object_y_center + object_height / 2) * image.height
                    draw.rectangle(
                        (object_x1, object_y1, object_x2, object_y2),
                        outline=self.class_colors[obj["class"]],
                        width=3,
                    )

            abs_subject_x_center = subject_x_center * image.width
            abs_subject_y_center = subject_y_center * image.height
            abs_object_x_center = object_x_center * image.width
            abs_object_y_center = object_y_center * image.height

            draw.line(
                (
                    abs_subject_x_center,
                    abs_subject_y_center,
                    abs_object_x_center,
                    abs_object_y_center,
                ),
                fill=self.predicate_colors[predicate_var.get()],
                width=3,
            )

            arrow_angle = 30
            angle = math.atan2(
                abs_object_y_center - abs_subject_y_center,
                abs_object_x_center - abs_subject_x_center,
            )
            angle1 = angle + math.radians(arrow_angle)
            angle2 = angle + math.radians(-arrow_angle)
            arrow_length = 20

            draw.line(
                (
                    abs_object_x_center - arrow_length * math.cos(angle1),
                    abs_object_y_center - arrow_length * math.sin(angle1),
                    abs_object_x_center,
                    abs_object_y_center,
                ),
                fill=self.predicate_colors[predicate_var.get()],
                width=3,
            )
            draw.line(
                (
                    abs_object_x_center - arrow_length * math.cos(angle2),
                    abs_object_y_center - arrow_length * math.sin(angle2),
                    abs_object_x_center,
                    abs_object_y_center,
                ),
                fill=self.predicate_colors[predicate_var.get()],
                width=3,
            )

            # 캔버스 초기화
            canvas.delete("all")

            tk_image.paste(image.resize((1280, 720)))
            canvas.create_image(640, 360, image=tk_image)
            canvas.image = tk_image

        # subject_id, predicate, object_id가 바뀔 때마다 이미지 다시 그리기
        subject_id_var.trace_add("write", update_image)
        predicate_var.trace_add("write", update_image)
        object_id_var.trace_add("write", update_image)

        # 수정 Dialog의 닫을때 실행되는 함수
        def close_edit_dialog():
            # Dialog가 닫힐 때 open_dialogs 리스트에서 해당 Dialog를 제거
            print("close_edit_dialog")
            self.open_dialogs.remove(edit_dialog)
            edit_dialog.destroy()

            # 만약 열린 edit_dialog가 남아있다면 마지막으로 열린 Dialog에 포커스를 맞춤
            if self.open_dialogs:
                # print("focus_set on last dialog")
                self.root.after(100, lambda: self.open_dialogs[-1].focus_set())
            else:
                # 남아있는 edit_dialog가 없다면 메인 창에 포커스를 맞춤
                # print("focus_set on root")
                self.root.after(100, lambda: self.root.focus_set())

        # 수정 Dialog의 확인 버튼 생성
        # 확인 버튼을 누르면 수정된 값으로 triple_key를 수정하고, 이미지를 다시 그림
        confirm_button = ttk.Button(
            edit_dialog,
            text="확인",
            command=lambda: self.confirm_edit_triple(
                triple_key,
                subject_id_var.get().split(": ")[1],
                predicate_var.get(),
                object_id_var.get().split(": ")[1],
                edit_dialog,
            ),
        )

        confirm_button.grid(row=1, column=2)

        # edit_dialog 닫기 버튼 설정 시 close_edit_dialog 호출
        edit_dialog.protocol("WM_DELETE_WINDOW", close_edit_dialog)

        def swap_subject_and_object(subject_id_var, object_id_var):
            tmp_subject_id = subject_id_var.get()
            subject_id_var.set(object_id_var.get())
            object_id_var.set(tmp_subject_id)

        reverse_arrow_button = ttk.Button(
            edit_dialog,
            text="화살표 방향 전환",
            command=lambda: swap_subject_and_object(subject_id_var, object_id_var)
        )

        reverse_arrow_button.grid(row=1, column=3)

        # Enter 키를 누르면 confirm_button이 클릭되도록 설정
        edit_dialog.bind("<Return>", lambda event: confirm_button.invoke())

        # 수정 Dialog 실행
        edit_dialog.mainloop()

    def confirm_edit_triple(
        self, triple_key, subject_id, predicate, object_id, edit_dialog
    ):
        # 현재 선택된 탭 저장
        self.last_selected_tab = self.notebook.index(self.notebook.select())

        # 중복 여부 확인
        new_triple_key = (int(subject_id), predicate, int(object_id))
        if new_triple_key in self.predicate_checkbuttons:
            # 중복된 triple_key가 있을 경우 에러 메시지 출력창을 띄움. 이떄 에러 메시지 출력창에는 확인 버튼과 삭제 버튼이 있음.
            error_dialog = tk.Toplevel(edit_dialog)
            error_dialog.title("중복된 Triple")
            error_dialog.geometry("300x100")

            error_label = tk.Label(
                error_dialog,
                text="이미 존재하는 Triple입니다.",
                font=("Helvetica", 12),
            )
            error_label.pack(pady=10)
            # 돌아가기 버튼을 누르면 에러 메시지 출력창을 닫고 edit_dialog에 포커스를 맞춤
            def close_error_dialog():
                error_dialog.destroy()
                edit_dialog.focus_set()

            confirm_button = ttk.Button(
                error_dialog,
                text="돌아가기",
                command=close_error_dialog,
            )

            # 삭제 버튼을 누르면 기존의 triple_key를 삭제하고, edit_dialog와 에러 메시지 출력창을 닫음
            def delete_triple_and_close():
                self.delete_triple(triple_key)
                error_dialog.destroy()
                self.open_dialogs.remove(edit_dialog)
                edit_dialog.destroy()

                # 만약 열린 edit_dialog가 남아있다면 마지막으로 열린 Dialog에 포커스를 맞춤
                if self.open_dialogs:
                    # print("focus_set on last dialog")
                    self.root.after(100, lambda: self.open_dialogs[-1].focus_set())
                else:
                    # 남아있는 edit_dialog가 없다면 메인 창에 포커스를 맞춤
                    # print("focus_set on root")
                    self.root.after(100, lambda: self.root.focus_set())

            delete_button = ttk.Button(
                error_dialog,
                text="수정 전 Triple 삭제",
                command=delete_triple_and_close,
            )

            # 확인버튼과 삭제버튼을 에러 메시지 출력창에 배치
            confirm_button.pack(side="left", padx=10)
            delete_button.pack(side="right", padx=10)

            # Enter 키를 누르면 confirm_button이 클릭되도록 설정
            error_dialog.bind("<Return>", lambda event: confirm_button.invoke())

            error_dialog.focus_set()
            return

        # subject_id와 object_id가 동일한 경우 에러 메시지 출력
        if subject_id == object_id:
            messagebox.showerror(
                title="동일한 ID",
                message="Subject ID와 Object ID는 동일할 수 없습니다.",
            )

            # 다이얼로그 화면으로 돌아가기
            edit_dialog.focus_set()
            return

        # 수정된 triple_key로 self.predicate_checkbuttons 수정
        self.predicate_checkbuttons[new_triple_key] = self.predicate_checkbuttons.pop(
            triple_key
        )

        # 수정된 triple_key로 self.vqa_data 수정
        for item in self.vqa_data:
            if item["image"]["image_name"] == os.path.basename(self.current_image):
                for triple in item["scene_graph"]["triples"]:
                    if (
                        triple["subject_id"] == triple_key[0]
                        and triple["predicate"] == triple_key[1]
                        and triple["object_id"] == triple_key[2]
                    ):
                        triple["subject_id"] = int(subject_id)
                        triple["predicate"] = predicate
                        triple["object_id"] = int(object_id)
                break

        # 수정 Dialog 종료
        edit_dialog.destroy()

        # 이미지 다시 그리기
        self.relation_triple_info_initialized = False
        self.display_image()

    def uncheck_relation_triples_except_current_tab(self):
        current_tab = self.notebook.select()

        # 현재 탭의 '전체 체크/해제' 체크 버튼을 항상 체크 상태로 변경
        for widget in self.notebook.nametowidget(current_tab).winfo_children():
            if isinstance(widget, ttk.Checkbutton) and widget['text'] == '전체 체크/해제':
                widget.state(['selected'])

        for tab_id in self.notebook.tabs():
            if tab_id != current_tab:
                tab_widget = self.notebook.nametowidget(tab_id)
                for index, child in enumerate(tab_widget.winfo_children()):
                    if isinstance(child, ttk.Checkbutton):
                        try:
                            if child['text'] != '전체 체크/해제':
                                self.predicate_checkbuttons[
                                    (
                                        int(child["text"].split(" - ")[0]),
                                        child["text"].split(" - ")[1],
                                        int(child["text"].split(" - ")[2]),
                                    )
                                ].set(False)
                        except KeyError:
                            pass
            else:
                tab_widget = self.notebook.nametowidget(tab_id)
                for child in tab_widget.winfo_children():
                    if isinstance(child, ttk.Checkbutton):
                        try:
                            if child['text'] != '전체 체크/해제':
                                self.predicate_checkbuttons[
                                    (
                                        int(child["text"].split(" - ")[0]),
                                        child["text"].split(" - ")[1],
                                        int(child["text"].split(" - ")[2]),
                                    )
                                ].set(True)
                        except KeyError:
                            pass
        self.display_image()

    def on_image_select(self, event):
        selected_index = self.image_listbox.curselection()
        if not selected_index:
            return

        selected_image = self.image_files[selected_index[0]]
        self.current_image = selected_image

        self.relation_triple_info_initialized = False
        self.last_selected_tab = None

        self.display_image()

    def on_canvas_resize(self, event):
        self.display_image()

    def get_random_color(self):
        import random

        r = lambda: random.randint(0, 255)
        return f"#{r():02x}{r():02x}{r():02x}"

    def class_and_predicate_random_color(self):
        self.class_colors = {cls: self.get_random_color() for cls in self.class_colors}
        self.predicate_colors = {
            predicate: self.get_random_color() for predicate in self.predicates
        }
        self.display_image()


if __name__ == "__main__":
    root = ThemedTk(theme="adapta")
    app = ImageLabelingApp(root)
    root.mainloop()
