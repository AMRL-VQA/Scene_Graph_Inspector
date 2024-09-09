import json
import random
from collections import Counter
from datetime import datetime
import re
from tqdm import tqdm
import glob
import os


# Bounding box에서 최소/최대 x, y 값 계산
def calculate_bounding_box_min_max(bbox):
    x_center, y_center, width, height = bbox
    x_min = x_center - width / 2
    x_max = x_center + width / 2
    
    y_center = 1 - y_center
    y_min = y_center - height / 2
    y_max = y_center + height / 2
    
    return x_center, x_min, x_max, y_center, y_min, y_max

# 물체가 겹쳐있음을 확인
def is_overlap(obj1, obj2):
    bbox_obj1 = obj1['bounding_box']
    bbox_obj2 = obj2['bounding_box']

    # rect1과 rect2는 각각 (x_min, y_min, x_max, y_max)로 이루어진 튜플이라고 가정
    obj1_x_center, obj1_x_min, obj1_x_max, obj1_y_center, obj1_y_min, obj1_y_max = calculate_bounding_box_min_max(bbox_obj1)
    obj2_x_center, obj2_x_min, obj2_x_max, obj2_y_center, obj2_y_min, obj2_y_max = calculate_bounding_box_min_max(bbox_obj2)
    
    # 2번이 1번에 완벽히 포함
    if obj1_x_min <= obj2_x_min and obj2_x_max <= obj1_x_max and\
        obj1_y_min <= obj2_y_min and obj2_y_max <= obj1_y_max:
        return '2->1 perfect'
    # 1번이 2번에 완벽히 포함
    elif obj2_x_min <= obj1_x_min and obj1_x_max <= obj2_x_max and\
        obj2_y_min <= obj1_y_min and obj1_y_max <= obj2_y_max:
        return '1->2 perfect'
    elif obj1_x_min < obj2_x_max and obj2_x_min < obj1_x_max and\
        obj1_y_min < obj2_y_max and obj2_y_min < obj1_y_max:
        return 'partial'
    # 겹쳐있지 않음
    else:
        return None

# Predicate 결정
def determine_predicate(sub, obj):
    portables = ['Rifle', 'Machine Gun', 'Sniper Rifle', 'Grenade Launcher', 'MANPATS', 'MANPADS']
    doors = ['Door', 'Window']
    vehicles = ['MBT', 'Vehicle', 'Artillery', 'MLRS', 'LUV', 'Truck']

    bbox_sub = sub['bounding_box']
    bbox_obj = obj['bounding_box']

    sub_x_center, sub_x_min, sub_x_max, sub_y_center, sub_y_min, sub_y_max = calculate_bounding_box_min_max(bbox_sub)
    obj_x_center, obj_x_min, obj_x_max, obj_y_center, obj_y_min, obj_y_max = calculate_bounding_box_min_max(bbox_obj)
    
    predicates = []

    # door 여부 확인 - [located in]
    if sub['class'] in doors:
        if obj['class'] == 'Building':
            if is_overlap(sub, obj) == '1->2 perfect':
                predicates.append("located in")
    else:
        if not sub['class'] in portables and\
            not obj['class'] in portables and\
            not obj['class'] in portables:
            # x축 비교: 왼쪽, 오른쪽 판단
            if obj_x_center < sub_x_min and obj_x_max < sub_x_center:
                predicates.append("to the right of")
            elif sub_x_center < obj_x_min and sub_x_max < obj_x_center:
                predicates.append("to the left of")
            
            sub_att = None
            obj_att = None
            # 비행중인 물체 비교
            if sub['attribute']:
                sub_att = sub['attribute'][0]
            if obj['attribute']:
                obj_att = obj['attribute'][0]
            if sub_att == 'Flying' or obj_att == 'Flying':
                if sub_att == 'Flying' and\
                    not obj_att == 'Flying':
                    predicates.append('above')
                elif (not sub_att == 'Flying') and\
                    obj_att == 'Flying':
                    predicates.append('below')
                elif sub_att == 'Flying' and\
                    obj_att == 'Flying':
                    predicates.append('both flying')                   
            elif obj_y_center < sub_y_min and obj_y_max < sub_y_center:
                predicates.append("behind")
            elif sub_y_center < obj_y_min and sub_y_max < obj_y_center:
                predicates.append("in front of")

    # 사람에 대한 판단 - [inside, holding, riding]
    if 'Infantry' in sub['class']:
        # portable 여부 파악
        if obj['class'] in portables:
            if is_overlap(sub, obj) is not None:
                predicates.append("holding")
        # inside 여부 파악
        elif obj['class'] == 'Building':
            if is_overlap(sub, obj) == '1->2 perfect':
                predicates.append("inside")
        # riding 여부 파악
        else:
            obj_class = re.split(r'\s', obj['class'])[-1]
            if obj_class in vehicles:
                if is_overlap(sub, obj) == '1->2 perfect':
                    predicates.append("riding")
    
    # 고층 건물에 대한 판단 - [N-story bulding]
    if sub['attribute']:
        if sub['class'] == 'Building':
            if sub['attribute']:
                sub_story = re.split(r'-', sub['attribute'][0])[0]
                if sub['attribute'] != 'One':
                    predicates.append("Multi-story")
                    
    return predicates


# Predicate pruning 함수
def prune_predicates(triples):
    if len(triples) <= 30:
        return triples
    
    # 무작위성을 위해 triple을 섞음
    random.shuffle(triples)

    # Predicate별 빈도수 계산
    predicate_count = Counter([triple['predicate'] for triple in triples])

    # left/right와 in front of/behind 그룹을 나눔
    freq_pred = None

    while len(triples) > 30:
        max_count = 0

        # 가장 빈도수가 많은 predicate 그룹 선택
        for pred in predicate_count:
            if predicate_count[pred] > max_count:
                max_count = predicate_count[pred]
                freq_pred = pred

        # 해당 predicate 중 하나를 삭제 (랜덤한 index)
        target_indexes = [i for i, triple in enumerate(triples) if triple['predicate'] == freq_pred]
        if target_indexes:
            random_index = random.choice(target_indexes)
            triples.pop(random_index)
            predicate_count[freq_pred] -= 1

            # 빈도가 0이 되면 해당 항목 삭제
            if predicate_count[freq_pred] == 0:
                del predicate_count[freq_pred]

        random.shuffle(triples)
    
    return triples

# JSON 파일 불러오기 및 처리
def process_scene_graph(scene_graph_file_name, ambiguity_file_name):
    try:
        # 파일 열기 시도
        with open(scene_graph_file_name, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        # 파일이 없을 경우 처리
        print(f"Error: File '{scene_graph_file_name}' not found.")
        return

    total_image_ambiguities = []
    ambiguities = ['holding', 'riding', 'inside', 'both flying', 'Multi-story']

    for image_data in tqdm(data):
        id = image_data['image']['image_id']
        image_id = f'image {id}'
        objects = image_data['scene_graph']['objects']
        triples = []
        image_ambiguities = {}

        # 각 물체 쌍에 대해 predicate 설정
        for i in range(len(objects)):
            for j in range(len(objects)):
                if i!= j:
                    sub = objects[i]
                    obj = objects[j]
                    predicates = determine_predicate(sub, obj)                    
                    
                    # 각 predicate에 대해 triples에 추가
                    for predicate in predicates:

                        if not (predicate == 'both flying' or predicates == 'Multi-story'):
                            triples.append({
                                "subject_id": sub['object_id'],
                                "predicate": predicate,
                                "object_id": obj['object_id']
                            })
                            
                        if predicate in ambiguities:
                            if not image_id in image_ambiguities:
                                image_ambiguities[image_id] = [predicate]
                            else:
                                if not predicate in image_ambiguities[image_id]:
                                    image_ambiguities[image_id].append(predicate)

        if image_ambiguities:
            image_ambiguities[image_id].sort()
            total_image_ambiguities.append(image_ambiguities)

        # Pruning 적용 (predicate가 30개 초과할 경우)
        triples = prune_predicates(triples)
        
        # 기존 triples 무시하고 새롭게 설정된 triples로 덮어쓰기
        image_data['scene_graph']['triples'] = triples
        
    # 결과를 새 파일로 저장
    scene_graph_path = process_file_name_with_date(scene_graph_file_name)
    with open(scene_graph_path, 'w') as f:
        json.dump(data, f, indent=4)
    
    ambiguity_path = process_file_name_with_date(ambiguity_file_name)
    with open(ambiguity_path, "w", encoding="utf-8") as f:
        json.dump(total_image_ambiguities, f, indent=4)
        

# 파일 이름 처리
def process_file_name_with_date(file_name):
    # 현재 날짜와 시간을 yyyy-mm-dd_hh-mm-ss 형식으로 가져옴
    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # 파일명에서 날짜와 시간 패턴(yyyy-mm-dd 또는 yyyy-mm-dd_hh-mm-ss)을 찾고 교체
    new_file_name = re.sub(r'\d{4}-\d{2}-\d{2}(_\d{2}-\d{2}-\d{2})?', current_datetime, file_name)

    # 만약 파일명에 날짜와 시간이 없으면 현재 날짜와 시간을 파일명 끝에 추가
    if new_file_name == file_name:  # 교체가 일어나지 않았을 때
        # 파일 확장자가 있으면 확장자 앞에 날짜와 시간 추가
        if '.' in file_name:
            base, ext = file_name.rsplit('.', 1)
            new_file_name = f"{base}_{current_datetime}.{ext}"
        else:
            new_file_name = f"{file_name}_{current_datetime}"
    
    return new_file_name

def find_graph_path(folder_path):
    # VQA_data_with_scene_graph.json 파일 읽기
        graph_path_list = glob.glob(os.path.join(folder_path, "json", "*.json"))
        graph_path_list.sort(
            key=lambda x: os.path.getmtime(x)
        )  # 날짜와 시간이 포함된 파일명을 기준으로 정렬
        graph_path = graph_path_list[-1]  # 가장 최근 파일 선택
        return graph_path

# test.json 파일 처리
graph_path = find_graph_path('./Dataset')
ambiguity_path = 'ambiguities.json'
process_scene_graph(graph_path, ambiguity_path)
