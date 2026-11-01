#!/usr/bin/env python3
"""
Central configuration, fixed 12-hour IST coverage window math,
and HTML/Google-News bundle sanitizer.
"""

import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ARCHIVE_DIR = ROOT_DIR / "archive"
SOURCES_FILE = DATA_DIR / "sources.json"
LATEST_EDITIONS_FILE = DATA_DIR / "latest-editions.json"
ARCHIVE_INDEX_FILE = DATA_DIR / "archive-index.json"
PIPELINE_LOGS_FILE = DATA_DIR / "pipeline-logs.json"

IST = timezone(timedelta(hours=5, minutes=30))

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
MAX_API_CALLS_PER_RUN = int(os.getenv("MAX_API_CALLS_PER_RUN", "2"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; TamilNaduPoliticsBrief/3.0; +https://github.com/tn-politics-brief)",
)

# Multi-word or unambiguous Tamil Nadu political party keywords
PARTY_TAXONOMY = {
    "DMK": [
        "dmk", "dravida munnetra kazhagam", "m.k. stalin", "mk stalin", "chief minister stalin",
        "cm stalin", "udhayanidhi", "kanimozhi", "திமுக", "மு.க.ஸ்டாலின்", "ஸ்டாலின்", "உதயநிதி"
    ],
    "AIADMK": [
        "aiadmk", "admk", "edappadi palaniswami", "palaniswami", "eps", "o. panneerselvam",
        "அதிமுக", "எடப்பாடி பழனிசாமி", "இபிஎஸ்"
    ],
    "BJP": [
        "bjp", "bharatiya janata party", "annamalai", "nainar nagendran", "l. murugan",
        "tamilisai", "பாஜக", "அண்ணாமலை", "நயினார் நாகேந்திரன்"
    ],
    "INC": [
        "tncc", "tamil nadu congress", "selvaperunthagai", "p. chidambaram", "karti chidambaram",
        "காங்கிரஸ்", "செல்வப்பெருந்தகை"
    ],
    "TVK": [
        "tvk", "tamilaga vettri kazhagam", "cm vijay", "chief minister vijay", "joseph vijay",
        "thalapathy vijay", "actor vijay", "vijay govt", "தவெக", "தமிழக வெற்றிக் கழகம்"
    ],
    "PMK": [
        "pmk", "pattali makkal katchi", "anbumani ramadoss", "s. ramadoss", "sowmiya anbumani",
        "பாமக", "அன்புமணி", "ராமதாஸ்"
    ],
    "NTK": [
        "ntk", "naam tamilar", "seeman", "நாம் தமிழர்", "சீமான்", "நாதக"
    ],
    "VCK": [
        "vck", "viduthalai chiruthaigal", "thirumavalavan", "விசிக", "விடுதலை சிறுத்தைகள்", "திருமாவளவன்"
    ],
    "MDMK": [
        "mdmk", "marumalarchi dravida", "vaiko", "durai vaiko", "மதிமுக", "வைகோ"
    ],
    "DMDK": [
        "dmdk", "desiya murpokku", "premalatha vijayakanth", "தேமுதிக", "பிரேமலதா"
    ],
    "AMMK": [
        "ammk", "amma makkal munnetra", "ttv dhinakaran", "dhinakaran", "அமமுக", "தினகரன்"
    ],
    "Left Parties": [
        "cpi(m)", "cpim", "cpi", "k. balakrishnan", "shanmugam", "mutharasan", "கம்யூனிஸ்ட்", "சிபிஎம்"
    ],
}

TOPIC_TAXONOMY = {
    "Government & Administration": [
        "cabinet", "chief minister", "secretariat", "government order", "collector",
        "welfare scheme", "da hike", "dearness allowance", "department", "police", "prison", "jailbreak"
    ],
    "Political Parties": [
        "alliance", "general council", "executive committee", "party meeting",
        "public meeting", "conference", "cadre", "bypoll", "byelection"
    ],
    "Assembly, Courts & Policy": [
        "assembly", "speaker", "madras high court", "madras hc", "madurai bench", "supreme court",
        "bill", "plea", "governor", "election commission", "local body election"
    ],
    "Elections": [
        "election", "by-election", "byelection", "bypoll", "constituency", "voter list",
        "electoral roll", "delimitation", "candidate"
    ],
    "Education & NEET": [
        "neet", "school education", "higher education", "university", "ugc", "professor", "college"
    ],
    "Agriculture & Water": [
        "farmer", "cauvery", "mullaperiyar", "kuruvai", "samba", "paddy", "procurement", "delta", "விவசாயி", "காவிரி", "முல்லைப் பெரியாறு", "நெல்", "டெல்டா"
    ],
    "Public Protests & Labour": [
        "protest", "demonstration", "strike", "detained", "agitators", "women's wing", "fishermen"
    ],
    "Centre–State Relations": [
        "union government", "centre", "gst", "finance commission", "delimitation", "india bloc"
    ],
    "Infrastructure & Economy": [
        "metro rail", "highway", "industrial", "investment", "sipcot", "power cut", "tangedco", "electricity"
    ],
}

TN_DISTRICTS = {
    "Ariyalur": ["ariyalur", "அரியலூர்"],
    "Chengalpattu": ["chengalpattu", "chengalpet", "maraimalai nagar", "செங்கல்பட்டு"],
    "Chennai": ["chennai", "ennore", "tambaram", "avadi", "சென்னை"],
    "Coimbatore": ["coimbatore", "kovai", "கோவை", "கோயம்புத்தூர்"],
    "Cuddalore": ["cuddalore", "chidambaram", "கடலூர்"],
    "Dharmapuri": ["dharmapuri", "தர்மபுரி", "தருமபுரி"],
    "Dindigul": ["dindigul", "திண்டுக்கல்"],
    "Erode": ["erode", "ஈரோடு"],
    "Kallakurichi": ["kallakurichi", "கள்ளக்குறிச்சி"],
    "Kancheepuram": ["kancheepuram", "kanchipuram", "காஞ்சிபுரம்"],
    "Kanniyakumari": ["kanniyakumari", "kanyakumari", "கன்னியாகுமரி", "குமரி"],
    "Karur": ["karur", "கரூர்"],
    "Krishnagiri": ["krishnagiri", "hosur", "கிருஷ்ணகிரி"],
    "Madurai": ["madurai", "மதுரை"],
    "Mayiladuthurai": ["mayiladuthurai", "மயிலாடுதுறை"],
    "Nagapattinam": ["nagapattinam", "நாகப்பட்டினம்", "நாகை"],
    "Namakkal": ["namakkal", "நாமக்கல்"],
    "Nilgiris": ["nilgiris", "ooty", "நீலகிரி", "ஊட்டி"],
    "Perambalur": ["perambalur", "பெரம்பலூர்"],
    "Pudukkottai": ["pudukkottai", "புதுக்கோட்டை"],
    "Ramanathapuram": ["ramanathapuram", "ராமநாதபுரம்"],
    "Ranipet": ["ranipet", "ராணிப்பேட்டை"],
    "Salem": ["salem", "சேலம்"],
    "Sivaganga": ["sivaganga", "sivagangai", "சிவகங்கை"],
    "Tenkasi": ["tenkasi", "தென்காசி"],
    "Thanjavur": ["thanjavur", "தஞ்சாவூர்", "தஞ்சை"],
    "Theni": ["theni", "தேனி"],
    "Thoothukudi": ["thoothukudi", "tuticorin", "தூத்துக்குடி"],
    "Tiruchirappalli": ["tiruchirappalli", "trichy", "திருச்சி", "திருச்சிராப்பள்ளி"],
    "Tirunelveli": ["tirunelveli", "nellai", "திருநெல்வேலி", "நெல்லை"],
    "Tirupathur": ["tirupathur", "திருப்பத்தூர்"],
    "Tiruppur": ["tiruppur", "திருப்பூர்"],
    "Tiruvallur": ["tiruvallur", "thiruvallur", "திருவள்ளூர்"],
    "Tiruvannamalai": ["tiruvannamalai", "திருவண்ணாமலை"],
    "Tiruvarur": ["tiruvarur", "thiruvarur", "திருவாரூர்"],
    "Vellore": ["vellore", "வேலூர்"],
    "Viluppuram": ["viluppuram", "villupuram", "விழுப்புரம்"],
    "Virudhunagar": ["virudhunagar", "விருதுநகர்"],
}

TN_RELEVANCE_KEYWORDS = [
    "tamil nadu", "tamilnadu", "t.n.", "tn govt", "tn cm", "madras high court", "madras hc"
]

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?rules", re.IGNORECASE),
    re.compile(r"<\s*/?\s*(script|iframe|style|system|instruction)[^>]*>", re.IGNORECASE),
]

TAMIL_UNICODE_RE = re.compile(r"[\u0B80-\u0BFF]")


def get_ist_now() -> datetime:
    return datetime.now(IST)


def compute_coverage_window(edition_type: str, target_date_str: str | None = None) -> dict:
    """
    Strictly locks the displayed Coverage Window:
    - Morning Edition: Previous day 6:00 PM IST to Current day 6:00 AM IST.
    - Evening Edition: Current day 6:00 AM IST to Current day 6:00 PM IST.
    Never shifts the displayed window to odd manual run minutes (like 10:22 AM or 11:22 PM).
    """
    now_ist = get_ist_now()
    if target_date_str:
        year, month, day = map(int, target_date_str.split("-"))
    else:
        year, month, day = now_ist.year, now_ist.month, now_ist.day

    edition_type = edition_type.strip().lower()
    if edition_type == "morning":
        end_dt = datetime(year, month, day, 6, 0, 0, tzinfo=IST)
        start_dt = end_dt - timedelta(hours=12)
        scheduled_dt = end_dt
        label = "Morning Brief"
    elif edition_type == "evening":
        end_dt = datetime(year, month, day, 18, 0, 0, tzinfo=IST)
        start_dt = datetime(year, month, day, 6, 0, 0, tzinfo=IST)
        scheduled_dt = end_dt
        label = "Evening Brief"
    else:
        raise ValueError(f"Invalid edition_type '{edition_type}'.")

    # Fetch window used internally by RSS collector (allows manual runs slightly after 6 AM/6 PM to still read current feeds)
    fetch_start_dt = start_dt
    fetch_end_dt = max(end_dt, now_ist) if target_date_str is None else end_dt

    date_str = scheduled_dt.strftime("%Y-%m-%d")
    human_date = scheduled_dt.strftime("%-d %B %Y") if os.name != "nt" else scheduled_dt.strftime("%d %B %Y").lstrip("0")
    edition_id = f"{date_str}-{edition_type}"

    return {
        "edition_id": edition_id,
        "date": date_str,
        "edition_type": edition_type,
        "title": f"Tamil Nadu Politics – {label} – {human_date}",
        "start_dt": fetch_start_dt,
        "end_dt": fetch_end_dt,
        "scheduled_dt": scheduled_dt,
        "coverage_start_ist": start_dt.isoformat(),
        "coverage_end_ist": end_dt.isoformat(),
        "scheduled_time_ist": scheduled_dt.isoformat(),
        "human_window": f"{start_dt.strftime('%d %b %Y, %I:%M %p IST')} – {end_dt.strftime('%d %b %Y, %I:%M %p IST')}",
    }


def sanitize_untrusted_text(text: str, max_length: int = 650) -> str:
    """
    Decodes HTML entities (&nbsp;, &#x1f537;), strips Google News multi-headline bundles,
    and removes TV/YouTube spam.
    """
    if not text:
        return ""

    raw = str(text)
    # If this is a Google News HTML bundle (<ol><li> or multiple <a href>), keep only the first item
    if "<li" in raw.lower():
        first_li = re.search(r"<li[^>]*>(.*?)</li>", raw, flags=re.IGNORECASE | re.DOTALL)
        if first_li:
            raw = first_li.group(1)

    # Cut off at &nbsp; before Google News appends Publisher Name or secondary headlines
    if "&nbsp;" in raw:
        raw = raw.split("&nbsp;")[0]

    # Decode HTML entities (&nbsp;, &#x1f537;, &amp;, etc.)
    cleaned = html.unescape(raw)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = cleaned.replace("\xa0", " ")

    # Cut off TV channel YouTube boilerplate
    cleaned = re.split(
        r"(?:WATCH\s+LIVE|Follow\s+US|Subscribe\s+to|ID_[A-Z0-9]+|https?://\S+)",
        cleaned,
        flags=re.IGNORECASE,
    )[0]

    # Remove emojis and symbols
    cleaned = re.sub(r"[\U00010000-\U0010ffff👉🔴📺▶️⚡🔔]+", " ", cleaned)
    cleaned = re.sub(r"^(?:JUST\s+NOW|BREAKING\s+NEWS|BREAKING|\d+\s*-\s*)\s*[\|:\-–—]?\s*", "", cleaned, flags=re.IGNORECASE)

    if cleaned.count("|") >= 2:
        parts = [p.strip() for p in cleaned.split("|") if len(p.strip()) > 3]
        cleaned = " — ".join(parts[:2]) if parts else cleaned

    cleaned = re.sub(r"(\|\s*){1,}", " ", cleaned)
    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[REDACTED_INSTRUCTION]", cleaned)

    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip(" |-–—:")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(" ", 1)[0] + "..."
    return cleaned


def has_tamil_script(text: str) -> bool:
    return bool(text and TAMIL_UNICODE_RE.search(text))


def translate_tamil_to_english(text: str) -> str:
    if not text:
        return ""
    if not has_tamil_script(text):
        return sanitize_untrusted_text(text)

    try:
        q = urllib.parse.quote(text[:900])
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ta&tl=en&dt=t&q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        translated_parts = [seg[0] for seg in data[0] if seg and seg[0]]
        result = "".join(translated_parts).strip()
        return sanitize_untrusted_text(result, max_length=650)
    except Exception:
        ascii_only = TAMIL_UNICODE_RE.sub(" ", text)
        return sanitize_untrusted_text(ascii_only, max_length=650)