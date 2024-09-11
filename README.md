# Scene Graph Generator

* v3 변경사항 (이하의 object는 목적어, 특정 물체는 '물체'로 언급) - edge 생성, pruning 알고리즘 개선
## edge 생성 알고리즘
0. 초기에 skipped, num_critical 변수는 0. 이번 알고리즘의 목적은 모든 물체간의 관계를 표현하는 최소한의 edge를 생성하는 것.
1. 전후좌우의 그래프 생성 순서 변경. left of 생성을 기준으로 x좌표값을 오름차순으로 정렬한 뒤, x 좌표값이 작은 물체부터 subject로 설정한 뒤 인접한 오른쪽 물체를 object로 두고 edge 생성.
2. 만약 해당 subject와 object가 left of 관계가 성립하지 않을 경우(겹쳐있음), object를 오른쪽으로 미루면서 left of가 성립하는지 확인.
3. 가장 오른쪽 물체까지 비교했는데도 left of가 성립하지 않으면, 해당 subject를 object로 설정하고, subject의 왼쪽에 있는 물체를 subject로 변경.
4. 이 때 left of가 성립할 때까지 subject를 왼쪽으로 미룸. 만약 left of를 고려하던 중에 이전에 생성되어 있던 edge랑 동일한 관계가 생성되면, skipped 변수값을 증가시킴.
5. 모든 물체를 비교한 후에 skipped 변수가 1 이상이면, 연결되지 않은 object들이 있는 것이므로 가장 오른쪽의 물체를 object로 두고 subject를 가장 오른쪽 물체부터 왼쪽으로 미루면서, 겹치지 않는 edge를 생성함. 생성할 때마다 skipped 값을 1씩 줄이고, skipped 값이 0이되면 종료.
6. left of 관계가 성립할 때마다 num_critical값을 증가시킴. 최종적으로 num_critical은 object의 수 - 1이 되어야 모든 물체간의 관계를 최소한으로 표현할 수 있음.
7. 이런 식으로 left -> right -> front -> behind 순으로 critical edge를 생성

## pruning 알고리즘
1. 위의 방식대로 edge를 생성하면 필수적인 edge들은 앞쪽에 몰려있게 됨. 해당 edge들의 마지막 index는 4 * (num_objects - 1) - 1
2. 필수 edge들의 마지막 index보다 큰 index의 edge들에 대해서만 pruning을 진행.
3. pruning의 기준은 필수 predicate(전후좌우)의 경우에는 각 predicate의 critical edge의 개수와 현재 edge의 개수의 차이를 기준으로, 부가적인 predicate들(above, riding 등)은 전체 개수를 기준으로, 가장 많은 predicate중 하나를 랜덤으로 삭제. 동일 개수의 predicate이 있으면 랜덤하게 선택됨.
4. 필수를 제외한 predicate이 모두 삭제되거나 edge의 개수가 30개 이하로 줄어들면 중단.

---

* v2 변경사항
1. 좌, 우, 앞, 뒤의 기준을 각 object의 중심이 서로의 바깥에 있어야함.
2. 문은 건물에 완전히 포함되어 있으면 located in으로 분류, located in 외의 관계는 생성하지 않음.
3. 비행중인 물체는 비행중이지 않은 물체들보다 위에 있음.
4. 직접 판단해야 하는 것들은 ambiguities.json파일로 저장
   1. 사람이 물건(총기류)를 들고있음, 총기류는 holding 외의 관계는 생성하지 않음.
   2. 사람이 차량에 타고있음
   3. 사람이 건물 내부에 있음
   4. 두 비행체가 모두 비행중
   5. 다층 건물의 경우 상 하를 직접 판단해야함


* 개선사항 후보군
1. 앞뒤좌우를 계산해야하는 두 물체의 일부가 겹쳐있을 때, 물체간의 각도를 계산해서 x축으로부터의 동경이 45도 미만이면 좌 or 우 / 45도 이상이면 앞 or 뒤
2. x값이 작은 순서대로 물체를 나열한 다음 그 순서대로 물체간의 left of를 계산, right of는 역순으로 계산
