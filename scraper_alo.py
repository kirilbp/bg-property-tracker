"""
Scrapes current Sofia apartment listings from alo.bg.
"""

import re
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PersonalDealTracker/1.0)"}
SEARCH_URL = "https://www.alo.bg/obiavi/imoti-prodajbi/apartamenti-stai/?region_id=22&location_ids=4342"
BASE_URL = "https://www.alo.bg"

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)
HISTORY_FILE = OUT_DIR / "history_alo.json"
LEADS_FILE = OUT_DIR / "leads_alo.json"

MAX_CARD_TEXT_LENGTH = 1500
MAX_PRICE_MENTIONS = 1

LISTING_LINK_RE = re.compile(r"^/[a-z0-9\-]+-(\d{6,9})$")
PRICE_RE = re.compile(r"\u0426\u0435\u043d\u0430:\s*([\d\s]+)\s?\u20ac")
SQM_RE = re.compile(r"\u041a\u0432\u0430\u0434\u0440\u0430\u0442\u0443\u0440\u0430:\s*([\d.,]+)\s?\u043a\u0432\.?\u043c")
AREA_RE = re.compile(r"((?:[\u0410-\u042f][\u0430-\u044f0-9]*\s+){0,3}[\u0410-\u042f][\u0430-\u044f0-9]*),\s
