"""
config/settings.py

DB 분석 시 자주 참조하는 값들을 모읍니다 (캠페인 필터 기준, 기간 계산 기준).

다른 파일에서는 이렇게 가져다 씁니다:
    from config.settings import CAMPAIGN_NAME_KEYWORDS, OBJECTIVE_MAP
"""

# ══════════════════════════════════════════════════════════════
#  ⚙️  캠페인 식별 필터 기준
# ══════════════════════════════════════════════════════════════
# 캠페인명에 아래 키워드 중 하나라도 포함되어야 대행 캠페인으로 인정
# (개별 브랜드사가 자체적으로 별도 캠페인을 돌릴 수 있어, 대행 캠페인만 골라내기 위한 필터)
CAMPAIGN_NAME_KEYWORDS = ["depart", "디파트"]

# campaigns.objective 매핑 (Meta 신구 체계 모두 포함, 2026-07-13 데이터로 확정 검증됨)
OBJECTIVE_MAP = {
    "traffic": ("OUTCOME_TRAFFIC", "LINK_CLICKS"),
    "sales": ("OUTCOME_SALES", "CONVERSIONS"),
}


# ══════════════════════════════════════════════════════════════
#  ⚙️  기간 계산 기준
# ══════════════════════════════════════════════════════════════
# 캠페인 식별 기간: 조회 주간의 월요일부터 +CREATION_WINDOW_DAYS일(기본 4 -> 금요일)까지
CREATION_WINDOW_DAYS = 4

# WoW/MoM 비교 시 기준으로 삼는 기간 이동 일수
WOW_OFFSET_DAYS = 7
MOM_OFFSET_DAYS = 28
