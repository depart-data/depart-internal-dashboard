"""
dashboard/pages/ai_evaluation.py

"AI 평가" 페이지 — 자리만 우선 만들어둔 페이지. 내용 미정.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from common import get_selected_account_id

st.title("AI 평가")

account_id = get_selected_account_id()

if account_id is None:
    st.info("사이드바에서 브랜드를 선택하세요.")
    st.stop()

st.divider()

st.info("자리만 우선 만들어둔 페이지입니다. 내용은 추후 결정.")
