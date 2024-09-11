import json
import random
from collections import Counter
from datetime import datetime
import re
from tqdm import tqdm
import glob
import os

portables = ['Rifle', 'Machine Gun', 'Sniper Rifle', 'Grenade Launcher', 'MANPATS', 'MANPADS']
doors = ['Door', 'Window']
vehicles = ['MBT', 'Vehicle', 'Artillery', 'MLRS', 'LUV', 'Truck']

ambiguities = ['holding', 'riding', 'inside', 'both flying', 'Multi-story']

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
            not obj['class'] in doors:
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

def generate_triple(sub, obj, predicate):
    triple = {
        "subject_id": sub['object_id'],
        "predicate": predicate,
        "object_id": obj['object_id']
    }

    return triple

# Predicate pruning 함수
def prune_predicates(triples, num_criticals):
    num_triples = len(triples)
    sum_criticals = sum(num_criticals.values())
    
    if num_triples <= 30:
        return triples
    
    # Predicate별 빈도수 계산
    predicate_count = Counter([triple['predicate'] for triple in triples])

    # 어떤 predicate이 지워질지 random으로 정하기 위해 섞음
    random.shuffle(predicate_count)

    # left/right와 in front of/behind 그룹을 나눔
    freq_pred = None

    while num_triples > 30:
        max_count = 0

        # 필수 predicate들은 필수값과 현재값의 차이로 계산해야 유의미함
        diff_count = {pred: (predicate_count[pred] - num_criticals[pred]) if pred in num_criticals else predicate_count[pred] for pred in predicate_count}

        # 필수 predicate들이 임계값에 다다르면 바로 return
        if all(diff_count[pred] == 0 for pred in num_criticals if pred in diff_count):
            return triples
        
        # 가장 빈도수가 많은 predicate 그룹 선택
        for pred in predicate_count:
            if diff_count[pred] > max_count:
                max_count = predicate_count[pred]
                freq_pred = pred

        # 전부 다 0개면 바로 종료
        if max_count == 0:
            return triples

        # 해당 predicate 중 하나를 삭제 (랜덤한 index)
        if freq_pred in num_criticals:
            target_indexes = [i for i, triple in enumerate(triples) if i >= sum_criticals and triple['predicate'] == freq_pred]
        else:
            target_indexes = [i for i, triple in enumerate(triples) if triple['predicate'] == freq_pred]
        if target_indexes:
            random_index = random.choice(target_indexes)
            triples.pop(random_index)
            predicate_count[freq_pred] -= 1

            # 빈도가 0이 되면 해당 항목 삭제
            if predicate_count[freq_pred] == 0:
                del predicate_count[freq_pred]

        num_triples = len(triples)
    
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

    for image_data in tqdm(data):
        id = image_data['image']['image_id']
        image_id = f'image {id}'
        objects = image_data['scene_graph']['objects']
        triples = []
        image_ambiguities = {}
        num_objects = len(objects)
        num_criticals = 0

        non_port_door = [obj for obj in objects if obj['class'] not in portables + doors]
        num_non_port_door = len(non_port_door)
        orderby_x = sorted(non_port_door, key=lambda obj: obj['bounding_box'][0])
        orderby_y = sorted(non_port_door, key=lambda obj: obj['bounding_box'][1], reverse=True)

        # 반드시 필요한 edge들의 수
        num_criticals = {'to the left of': 0, 
                         'to the right of': 0, 
                         'in front of': 0, 
                         'behind': 0}
        add_triple = 0

        # 필수 left 생성
        skipped = 0
        target_pred = 'to the left of'
        for i in range(num_non_port_door):
            if i == num_non_port_door - 1:
                ti = i - 1
                j = i
                while skipped > 0 and 0 <= ti:
                    if target_pred in determine_predicate(orderby_x[ti],orderby_x[j]):
                        triple = generate_triple(orderby_x[ti], orderby_x[j], target_pred)
                        if triple in triples:
                            ti -= 1
                            continue
                        triples.append(triple)
                        skipped -= 1
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1
            else:         
                ti = i
                j = ti + 1
                while j < num_non_port_door:
                    if target_pred in determine_predicate(orderby_x[ti],orderby_x[j]):
                        triple = generate_triple(orderby_x[ti], orderby_x[j], target_pred)
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        add_triple = 1
                        break
                    j += 1
                if add_triple:
                    add_triple = 0
                    continue
                j = ti
                while 0 <= ti:
                    if target_pred in determine_predicate(orderby_x[ti],orderby_x[j]):
                        triple = generate_triple(orderby_x[ti], orderby_x[j], target_pred)
                        if triple in triples:
                            skipped += 1
                            ti -= 1
                            break
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1
        
        orderby_x.reverse()
        # 필수 right 생성
        skipped = 0
        target_pred = 'to the right of'
        for i in range(num_non_port_door):
            if i == num_non_port_door - 1:
                ti = i - 1
                j = i
                while skipped > 0 and 0 <= ti:
                    if target_pred in determine_predicate(orderby_x[ti],orderby_x[j]):
                        triple = generate_triple(orderby_x[ti], orderby_x[j], target_pred)
                        if triple in triples:
                            ti -= 1
                            continue
                        triples.append(triple)
                        skipped -= 1
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1
            else:         
                ti = i
                j = ti + 1
                while j < num_non_port_door:
                    if target_pred in determine_predicate(orderby_x[ti],orderby_x[j]):
                        triple = generate_triple(orderby_x[ti], orderby_x[j], target_pred)
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        add_triple = 1
                        break
                    j += 1
                if add_triple:
                    add_triple = 0
                    continue
                j = ti
                while 0 <= ti:
                    if target_pred in determine_predicate(orderby_x[ti],orderby_x[j]):
                        triple = generate_triple(orderby_x[ti], orderby_x[j], target_pred)
                        if triple in triples:
                            skipped += 1
                            ti -= 1
                            break
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1

        # 필수 in front of 생성
        skipped = 0
        target_pred = 'in front of'
        for i in range(num_non_port_door):
            if i == num_non_port_door - 1:
                ti = i - 1
                j = i
                while skipped > 0 and 0 <= ti:
                    if target_pred in determine_predicate(orderby_y[ti],orderby_y[j]):
                        triple = generate_triple(orderby_y[ti], orderby_y[j], target_pred)
                        if triple in triples:
                            ti -= 1
                            continue
                        triples.append(triple)
                        skipped -= 1
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1
            else:         
                ti = i
                j = ti + 1
                while j < num_non_port_door:
                    if target_pred in determine_predicate(orderby_y[ti],orderby_y[j]):
                        triple = generate_triple(orderby_y[ti], orderby_y[j], target_pred)
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        add_triple = 1
                        break
                    j += 1
                if add_triple:
                    add_triple = 0
                    continue
                j = ti
                while 0 <= ti:
                    if target_pred in determine_predicate(orderby_y[ti],orderby_y[j]):
                        triple = generate_triple(orderby_y[ti], orderby_y[j], target_pred)
                        if triple in triples:
                            skipped += 1
                            ti -= 1
                            break
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1

        orderby_y.reverse()
        # 필수 behind 생성
        skipped = 0
        target_pred = 'behind'
        for i in range(num_non_port_door):
            if i == num_non_port_door - 1:
                ti = i - 1
                j = i
                while skipped > 0 and 0 <= ti:
                    if target_pred in determine_predicate(orderby_y[ti],orderby_y[j]):
                        triple = generate_triple(orderby_y[ti], orderby_y[j], target_pred)
                        if triple in triples:
                            ti -= 1
                            continue
                        triples.append(triple)
                        skipped -= 1
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1
            else:         
                ti = i
                j = ti + 1
                while j < num_non_port_door:
                    if target_pred in determine_predicate(orderby_y[ti],orderby_y[j]):
                        triple = generate_triple(orderby_y[ti], orderby_y[j], target_pred)
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        add_triple = 1
                        break
                    j += 1
                if add_triple:
                    add_triple = 0
                    continue
                j = ti
                while 0 <= ti:
                    if target_pred in determine_predicate(orderby_y[ti],orderby_y[j]):
                        triple = generate_triple(orderby_y[ti], orderby_y[j], target_pred)
                        if triple in triples:
                            skipped += 1
                            ti -= 1
                            break
                        triples.append(triple)
                        num_criticals[target_pred] += 1
                        break
                    ti -= 1

        
        # 각 물체 쌍에 대해 predicate 설정
        for i in range(num_objects):
            for j in range(num_objects):
                if i!= j:
                    sub = objects[i]
                    obj = objects[j]
                    predicates = determine_predicate(sub, obj)             
                    
                    # 각 predicate에 대해 필수적이지 않은 triples에 추가
                    for predicate in predicates:
                        if not (predicate == 'both flying' or predicates == 'Multi-story'):
                            triple = generate_triple(sub, obj, predicate)
                            if triple not in triples:
                                # triples.append(triple)
                                pass
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
        triples = prune_predicates(triples, num_criticals)
        
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