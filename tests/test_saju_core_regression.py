# 파일 경로: tests/test_saju_core_regression.py
#
# 목적: core/saju_base.py, core/sipsin.py, core/interactions.py가 앞으로 리팩토링되어도
# "이미 검증된 핵심 계산값"이 실수로 바뀌지 않았는지 자동으로 감시하는 회귀 테스트.
#
# 이 파일은 기존 코드를 전혀 수정하지 않습니다. 새로 추가하는 테스트 파일입니다.
#
# 실행 방법: pip install pytest 후 `pytest tests/test_saju_core_regression.py -v`
#
# 설계 원칙:
# 1. "현재 Saju Core가 실제로 계산하는 값"만 테스트 대상으로 포함한다.
#    (신살/용신/12운성처럼 아직 구현 안 된 항목은 xfail로 표시해서,
#     "구현이 안 됐다"는 사실 자체를 테스트가 계속 상기시키게 한다.)
# 2. 값은 추정이 아니라 실제 실행 + 독립 검증(한국민족문화대백과사전 기준일 대조)을 거친 값만 사용한다.
# 3. 오케스트레이션 계층(core/saju_base.py 전체)이 지금은 import 에러로 실행 자체가 안 되므로,
#    - (A) 하부 순수 함수 단위 테스트(sipsin, interactions)는 지금 당장 실행 가능하게 만들고
#    - (B) calculate_saju() 전체 통합 테스트는 "현재는 반드시 실패해야 정상"인 상태로 명시해서
#      나중에 import 버그가 고쳐지는 순간 이 테스트가 자동으로 통과 여부를 알려주게 한다.

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ============================================================
# 검증된 테스트 벡터 (Golden Values)
# 출생정보: 1983-05-14, 14:00, 서울, 여성
# 검증 방법: sajupy 실제 실행 + 한국민족문화대백과사전 기준일(1981-01-01=己卯)
#           기반 독립 날짜 계산으로 교차 검증 완료 (일치 확인됨)
# ============================================================

TEST_CASE_1 = {
    "input": {"year": 1983, "month": 5, "day": 14, "hour": 14, "minute": 0, "gender": "female"},
    "expected": {
        "year_pillar": "癸亥",
        "month_pillar": "丁巳",
        "day_pillar": "壬寅",
        "hour_pillar": "丁未",
        "day_master": "壬",
        "day_branch": "寅",
        "five_elements": {"목": 1, "화": 3, "토": 1, "금": 0, "수": 3},
        "sipsin": {
            "year_gan": "겁재", "year_ji": "겁재",
            "month_gan": "정재", "month_ji": "정재",
            "day_gan": "비견", "day_ji": "식신",
            "hour_gan": "정재", "hour_ji": "정관",
        },
        # 육합/충만 검출 가능한 현재 코드 기준. 寅-巳 형(刑)은 구현이 안 되어 있어
        # 아래 목록에는 포함되어 있지 않음 -> test_interactions_missing_hyeong이 이 격차를 명시적으로 잡아냄
        "ji_interactions": ["육합(寅-亥)", "충(巳-亥)"],
        # daewoon_num 검증: 년간 癸(음간) + 여성 -> 음녀 = 순행.
        # 순행이므로 다음 절입(1983-06-06 15:02 망종)까지 23.04일 -> 23.04/3 반올림 = 8.
        # calculate_exact_daewoon_num()이 timedelta(days=15) 고정값 버그로 항상 5를 반환하던
        # 것을 sajupy 내장 실제 절기 정밀시각(calendar_data.csv) 기반으로 수정한 뒤의 검증값.
        "daewoon_num": 8,
        "daewoon_direction": "순행",
    }
}

# 경계값/특수 케이스 추가 - 앞으로 계속 채워나갈 자리
# 각 항목은 실제 만세력과 대조 검증 후에만 expected 값을 채워 넣을 것 (임의 추정 금지)
ADDITIONAL_TEST_CASES = [
    {
        "name": "자시(23:30) 경계 - 야자시/조자시 처리 확인용",
        "input": {"year": 1990, "month": 6, "day": 15, "hour": 23, "minute": 30, "gender": "male"},
        "expected": None,  # TODO: 실제 만세력 대조 후 채우기
    },
    {
        "name": "절기 경계 - 입춘 직전 출생 (연주 보정 확인용)",
        "input": {"year": 2000, "month": 2, "day": 3, "hour": 10, "minute": 0, "gender": "female"},
        "expected": None,  # TODO: 입춘 전이므로 전년도 간지가 나오는지 확인
    },
    {
        "name": "윤년 2월 29일 출생",
        "input": {"year": 1996, "month": 2, "day": 29, "hour": 8, "minute": 0, "gender": "male"},
        "expected": None,  # TODO
    },
    {
        "name": "출생시간 미상 케이스",
        "input": {"year": 1983, "month": 5, "day": 14, "hour": None, "minute": 0, "gender": "female"},
        "expected": None,  # TODO: 시주는 '미정'이어야 하고 시주 의존 요소가 계산에서 제외되는지 확인
    },
]


# ============================================================
# A. sajupy 원국 계산 - 사주 엔진의 최하단, 가장 먼저 보호해야 할 계층
# ============================================================
class TestSajuPillars:
    def test_pillars_match_verified_values(self):
        """
        sajupy가 4주(년/월/일/시)를 올바르게 계산하는지 확인.
        이 테스트가 실패하면 sajupy 라이브러리 버전이 바뀌었거나
        city/use_solar_time 등 호출 파라미터가 바뀐 것이므로 반드시 원인을 확인해야 함.
        """
        import sajupy
        case = TEST_CASE_1
        result = sajupy.calculate_saju(
            case["input"]["year"], case["input"]["month"], case["input"]["day"],
            case["input"]["hour"], case["input"]["minute"],
            city="Seoul", use_solar_time=True
        )
        assert result["year_pillar"] == case["expected"]["year_pillar"]
        assert result["month_pillar"] == case["expected"]["month_pillar"]
        assert result["day_pillar"] == case["expected"]["day_pillar"]
        assert result["hour_pillar"] == case["expected"]["hour_pillar"]
        assert result["day_stem"] == case["expected"]["day_master"]
        assert result["day_branch"] == case["expected"]["day_branch"]

    def test_solar_time_geocoding_fallback_is_logged(self, caplog):
        """
        진태양시 보정을 위한 지오코딩이 실패했을 때 '조용히' 표준시로
        넘어가지 않고 최소한 경고가 남는지 확인.
        (배포 환경의 네트워크 상태에 따라 시주가 바뀔 수 있는 리스크를 감시하는 테스트)
        주의: 이 테스트는 지오코딩 성공/실패 여부에 따라 결과가 달라질 수 있으므로
        CI 환경에 따라 skip 처리가 필요할 수 있음.
        """
        pytest.skip("네트워크 의존적 테스트 - 실제 배포 환경에서 별도로 수동 확인 필요")


# ============================================================
# B. 십신 계산 - core/sipsin.py 순수 함수 단위 테스트
# ============================================================
class TestSipsin:
    @pytest.fixture(autouse=True)
    def setup(self):
        from core.sipsin import calculate_sipsin, GAN_FIVE_ELEMENTS, JI_FIVE_ELEMENTS
        self.calculate_sipsin = calculate_sipsin
        self.GAN_FIVE_ELEMENTS = GAN_FIVE_ELEMENTS
        self.JI_FIVE_ELEMENTS = JI_FIVE_ELEMENTS

    def test_sipsin_matches_verified_values(self):
        case = TEST_CASE_1["expected"]
        day_master = case["day_master"]
        pillars = {
            "year": ("癸", "亥"), "month": ("丁", "巳"),
            "day": ("壬", "寅"), "hour": ("丁", "未"),
        }
        for name, (gan, ji) in pillars.items():
            assert self.calculate_sipsin(day_master, gan, is_gan=True) == case["sipsin"][f"{name}_gan"]
            assert self.calculate_sipsin(day_master, ji, is_gan=False) == case["sipsin"][f"{name}_ji"]

    def test_five_elements_count_matches(self):
        """
        five_elements 집계 - 주의: 현재 core/saju_base.py는 이 집계를
        반환값에 포함하지 않는 버그가 있음. 이 테스트는 sipsin.py의
        딕셔너리 자체가 정확한지만 확인하는 하위 레벨 테스트.
        saju_base.py가 고쳐지면 test_integration.py 쪽에 통합 테스트를 추가할 것.
        """
        case = TEST_CASE_1["expected"]
        pillars = [("癸", "亥"), ("丁", "巳"), ("壬", "寅"), ("丁", "未")]
        counts = {"목": 0, "화": 0, "토": 0, "금": 0, "수": 0}
        for gan, ji in pillars:
            counts[self.GAN_FIVE_ELEMENTS[gan]] += 1
            counts[self.JI_FIVE_ELEMENTS[ji]] += 1
        assert counts == case["five_elements"]

    @pytest.mark.parametrize("day_master,target,is_gan,expected", [
        ("甲", "甲", True, "비견"),
        ("甲", "乙", True, "겁재"),
        ("甲", "丙", True, "식신"),
        ("甲", "丁", True, "상관"),
        ("甲", "戊", True, "편재"),
        ("甲", "己", True, "정재"),
        ("甲", "庚", True, "편관"),
        ("甲", "辛", True, "정관"),
        ("甲", "壬", True, "편인"),
        ("甲", "癸", True, "정인"),
    ])
    def test_sipsin_full_matrix_from_gap_day_master(self, day_master, target, is_gan, expected):
        """
        일간=甲 기준으로 10천간 전체에 대한 십신 표가 표준 명리학 정의와
        일치하는지 전수 검사. (다른 일간으로 확장 가능한 템플릿)
        """
        assert self.calculate_sipsin(day_master, target, is_gan=is_gan) == expected


# ============================================================
# C. 지지 상호작용 - core/interactions.py
# ============================================================
class TestInteractions:
    @pytest.fixture(autouse=True)
    def setup(self):
        from core.interactions import check_ji_interactions
        self.check_ji_interactions = check_ji_interactions

    def test_interactions_match_verified_values(self):
        case = TEST_CASE_1["expected"]
        jis = ["亥", "巳", "寅", "未"]  # 년/월/일/시 순
        result = self.check_ji_interactions(jis)
        for expected_item in case["ji_interactions"]:
            assert expected_item in result

    @pytest.mark.xfail(reason="형(刑) 미구현 - core/interactions.py는 육합/충/자형만 계산함. "
                               "寅-巳는 실제 인사형(寅巳刑) 관계이나 현재 코드가 감지하지 못함.")
    def test_interactions_detects_hyeong(self):
        """
        寅-巳 형(刑) 관계 감지 테스트. 형/파/해 구현 완료 시 이 테스트가
        xfail에서 pass로 바뀌어야 함 -> pytest.ini에서 xfail_strict=True로 설정해두면
        구현 완료 시 "예상치 못한 성공(XPASS)"으로 표시되어 바로 알아챌 수 있음.
        """
        result = self.check_ji_interactions(["亥", "巳", "寅", "未"])
        assert any("형" in item and "寅" in item and "巳" in item for item in result)

    @pytest.mark.parametrize("ji_list,should_contain", [
        (["子", "丑"], "육합(子-丑)"),
        (["寅", "亥"], "육합(寅-亥)"),
        (["子", "午"], "충(子-午)"),
        (["卯", "酉"], "충(卯-酉)"),
        (["辰", "辰"], "자형(辰-辰)"),
        (["午", "午"], "자형(午-午)"),
    ])
    def test_known_interaction_pairs(self, ji_list, should_contain):
        result = self.check_ji_interactions(ji_list)
        assert should_contain in result


# ============================================================
# D. 아직 구현되지 않은 항목 - "없다"는 사실 자체를 감시
# ============================================================
class TestNotYetImplemented:
    """
    이 클래스의 테스트들은 지금은 전부 xfail이 '정상'입니다.
    누군가 신살/용신/12운성을 구현하면 이 테스트들이 XPASS로 뜨면서
    "이제 이 기능을 진짜 테스트로 승격시켜야 한다"는 신호를 줍니다.
    """

    @pytest.mark.xfail(reason="신살(역마/도화/화개 등) 계산 로직이 리포지토리 어디에도 없음")
    def test_sinsal_yeokma_detected(self):
        # 1983-05-14 사주(년지 亥, 월지 巳)는 해묘미 그룹 역마=巳 규칙상
        # 역마살 후보로 보이나, 실제 계산 코드가 없어 검증 불가
        pytest.fail("신살 계산 함수가 존재하지 않음")

    @pytest.mark.xfail(reason="용신/희신/기신/격국 계산 로직이 리포지토리 어디에도 없음")
    def test_yongsin_calculated(self):
        pytest.fail("용신 계산 함수가 존재하지 않음")

    @pytest.mark.xfail(reason="12운성(장생/목욕/관대 등) 계산 로직이 리포지토리 어디에도 없음")
    def test_twelve_unseong_calculated(self):
        pytest.fail("12운성 계산 함수가 존재하지 않음")


# ============================================================
# E. 오케스트레이션 계층 통합 테스트 - 지금은 반드시 실패해야 정상
# ============================================================
class TestSajuBaseIntegration:
    # [해결됨] core.daewoon 함수명 불일치 수정 완료 -> 실제 통합 테스트로 승격
    def test_calculate_saju_end_to_end_runs(self):
        from core.saju_base import calculate_saju
        result = calculate_saju(
            year=1983, month=5, day=14, hour=14, minute=0, gender="female"
        )
        assert result["day_master"] == "壬"
        assert result["birth_ganji"]["day"] == "壬寅"

    # [해결됨] calculate_saju() 반환값에 플랫 키(year_ganji 등) + five_elements 추가 완료
    def test_calculate_saju_returns_flat_keys_for_other_domains(self):
        from core.saju_base import calculate_saju
        result = calculate_saju(year=1983, month=5, day=14, hour=14, minute=0, gender="female")
        assert result.get("year_ganji") == "癸亥"
        assert result.get("day_ganji") == "壬寅"
        assert result.get("five_elements") == TEST_CASE_1["expected"]["five_elements"]


# ============================================================
# E-2. 대운수(daewoon_num) - core/daewoon.py의 calculate_exact_daewoon_num()
#
# 과거 버그: 실제 절기 계산 대신 timedelta(days=15) 고정값을 써서 생년월일과
# 무관하게 항상 daewoon_num=5가 나왔음. sajupy 패키지에 내장된 1900~2100년
# 절기 정밀시각 테이블(calendar_data.csv, KASI 기준) 기반으로 수정.
# 이 클래스가 실패하면 "항상 5" 버그가 재발했을 가능성이 높음.
# ============================================================
class TestDaewoonNum:
    @pytest.fixture(autouse=True)
    def setup(self):
        from core.daewoon import calculate_exact_daewoon_num, calculate_daewoon_info
        self.calculate_exact_daewoon_num = calculate_exact_daewoon_num
        self.calculate_daewoon_info = calculate_daewoon_info

    def test_daewoon_num_matches_verified_value_for_test_case_1(self):
        """
        1983-05-14 14:00 여성 케이스. 순행이므로 다음 절입(1983-06-06 15:02 망종)까지
        23.04일 -> 3일=1년 반올림 기준 daewoon_num=8. 타 만세력 서비스에서 8세 근처로
        나온다는 사용자 보고와 일치.
        """
        from datetime import datetime
        case = TEST_CASE_1["expected"]
        birth_dt = datetime(1983, 5, 14, 14, 0)
        assert self.calculate_exact_daewoon_num(birth_dt, is_forward=True) == case["daewoon_num"]

    def test_daewoon_num_end_to_end_via_calculate_daewoon_info(self):
        case = TEST_CASE_1["expected"]
        result = self.calculate_daewoon_info(
            1983, 5, 14, "female",
            year_pillar=case["year_pillar"], month_pillar=case["month_pillar"],
        )
        assert result["daewoon_num"] == case["daewoon_num"]
        assert result["direction"] == case["daewoon_direction"]

    @pytest.mark.parametrize("year,month,day,hour,is_forward", [
        (1983, 5, 14, 14, True),
        (1983, 5, 14, 14, False),
        (1990, 1, 1, 0, True),
        (1975, 3, 15, 9, False),
        (2001, 7, 20, 18, True),
        (1965, 6, 6, 3, False),
        (2010, 2, 3, 12, True),
        (1955, 11, 11, 21, False),
        (1999, 9, 9, 6, True),
        (2020, 4, 30, 15, False),
    ])
    def test_daewoon_num_is_not_always_five(self, year, month, day, hour, is_forward):
        """
        회귀 방지의 핵심: 과거 버그는 '항상 5'였다. 서로 다른 절기 구간에 걸친
        10개 생년월일 중 전부가 5로 뭉치면 안 되고, 각 값은 1~10 범위 안에 있어야 한다.
        (이 테스트 하나만으로는 "우연히 전부 5"인 경우를 못 걸러내므로,
        test_daewoon_num_values_are_not_all_identical 이 그 보완 역할을 한다.)
        """
        from datetime import datetime
        num = self.calculate_exact_daewoon_num(datetime(year, month, day, hour), is_forward)
        assert 1 <= num <= 10

    def test_daewoon_num_values_are_not_all_identical(self):
        """
        서로 다른 10개 생년월일의 daewoon_num이 전부 같은 값(=버그였던 5)으로
        뭉치지 않고 실제로 흩어지는지 확인 - 'timedelta(days=15) 고정값' 버그의
        직접적인 재발 감시 테스트.
        """
        from datetime import datetime
        inputs = [
            (1983, 5, 14, 14, True), (1990, 1, 1, 0, True), (1975, 3, 15, 9, False),
            (2001, 7, 20, 18, True), (1965, 6, 6, 3, False), (2010, 2, 3, 12, True),
            (1955, 11, 11, 21, False), (1999, 9, 9, 6, True), (2020, 4, 30, 15, False),
            (1970, 8, 8, 10, True),
        ]
        results = {
            self.calculate_exact_daewoon_num(datetime(y, m, d, hh), fwd)
            for y, m, d, hh, fwd in inputs
        }
        assert len(results) > 1, f"모든 daewoon_num이 동일한 값으로 뭉침: {results} (항상 5 버그 재발 의심)"
        assert results != {5}, "daewoon_num이 항상 5 - timedelta(days=15) 고정값 버그가 재발한 것으로 보임"


# ============================================================
# F. 앞으로 테스트 케이스를 채워나가기 위한 뼈대
# ============================================================
@pytest.mark.parametrize("case", [c for c in ADDITIONAL_TEST_CASES if c["expected"] is not None])
def test_additional_verified_cases(case):
    """
    ADDITIONAL_TEST_CASES에 expected 값이 채워지는 즉시 이 테스트가 자동으로 실행 대상에 포함됨.
    지금은 전부 expected=None이라 parametrize 목록이 비어 있고, 아무 것도 실행되지 않음.
    반드시 실제 만세력과 대조 검증한 값만 채워 넣을 것 (추정 금지).
    """
    pass  # TODO: 값이 채워지면 core.saju_base.calculate_saju 호출 후 assert 작성
