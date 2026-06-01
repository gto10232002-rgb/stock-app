import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
import yfinance as yf

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==========================================
# 0. 頁面設定 / 手機友善 CSS
# ==========================================
st.set_page_config(
    page_title="StockTool",
    layout="wide",
)

st.markdown(""
<style>
    .block-container {
        padding-top: 1.0rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 1200px;
    }

    h1, h2, h3 {
        margin-top: 0rem !important;
        margin-bottom: 0.4rem !important;
    }

    .mobile-card {
        border: 1px solid rgba(180,180,180,0.25);
        border-radius: 14px;
        padding: 14px 14px 10px 14px;
        margin-bottom: 10px;
        background: rgba(255,255,255,0.02);
    }

    .mobile-title {
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
        line-height: 1.35;
    }

    .mobile-sub {
