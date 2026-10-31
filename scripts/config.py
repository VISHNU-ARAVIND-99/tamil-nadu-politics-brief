#!/usr/bin/env python3
"""
Central configuration, IST timezone calculation, Tamil & English political taxonomies,
district registries, and automatic Tamil-to-English translation helper.
"""

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
    "Mozilla/5.0 (compatible; TamilNaduPoliticsBrief/2.0; +https://github.com/tn-politics-brief)",
)

PARTY_TAXONOMY = {
    "DMK": [
        "dmk", "dravida munnetra kazhagam", "mk stalin", "m.k. stalin", "udhayanidhi stalin",
        "kanimozhi", "திமுக", "திராவிட முன்னேற்றக் கழகம்", "மு.க.ஸ்டாலின்", "ஸ்டாலின்", "உதயநிதி"
    ],
    "AIADMK": [
        "aiadmk", "admk", "all india anna dravida munnetra kazhagam", "edappadi palaniswami",
        "eps", "ops", "அதிமுக", "அண்ணா திராவிட முன்னேற்றக் கழகம்", "எடப்பாடி பழனிசாமி", "இபிஎஸ்"
    ],
    "BJP": [
        "bjp", "bharatiya janata party", "annamalai", "nainar nagendran", "l murugan",
        "tamilisai", "பாஜக", "பாரதிய ஜனதா", "அண்ணாமலை", "நயினார் நாகேந்திரன்"
    ],
    "INC": [
        "congress", "tncc", "indian national congress", "selvaperunthagai", "p chidambaram",
        "காங்கிரஸ்", "செல்வப்பெருந்தகை", "தமிழ்நாடு காங்கிரஸ்"
    ],
    "TVK": [
        "tvk", "tamilaga vettri kazhagam", "vijay", "thalapathy vijay", "panaiyur",
        "தவெக", "தமிழக வெற்றிக் கழகம்", "விஜய்"
    ],
    "PMK": [
        "pmk", "pattali makkal katchi", "anbumani ramadoss", "ramadoss",
        "பாமக", "பாட்டாளி மக்கள் கட்சி", "அன்புமணி", "ராமதாஸ்"
    ],
    "NTK": [
        "ntk", "naam tamilar katchi", "seeman", "நாம் தமிழர்", "சீமான்", "நாதக"
    ],
    "VCK": [
        "vck", "viduthalai chiruthaigal katchi", "thol thirumavalavan", "thirumavalavan",
        "விசிக", "விடுதலை சிறுத்தைகள்", "திருமாவளவன்"
    ],
    "MDMK": [
        "mdmk", "marumalarchi dravida munnetra kazhagam", "vaiko", "durai vaiko",
        "மதிமுக", "வைகோ", "துரை வைகோ"
    ],
    "DMDK": [
        "dmdk", "desiya murpokku dravida kazhagam", "premalatha vijayakanth",
        "தேமுதிக", "பிரேமலதா விஜயகாந்த்"
    ],
    "AMMK": [
        "ammk", "amma makkal munnetra kazhagam", "ttv dhinakaran", "dhinakaran",
        "அமமுக", "டிடிவி தினகரன்", "தினகரன்"
    ],
    "Left Parties": [
        "cpi(m)", "cpim", "cpi", "communist party", "k balakrishnan", "shanmugam",
        "r mutharasan", "கம்யூனிஸ்ட்", "மார்க்சிஸ்ட்", "சிபிஎம்", "சிபிஐ"
    ],
}

TOPIC_TAXONOMY = {
    "Government & Administration": [
        "cabinet", "chief minister", "secretariat", "government order", "collector",
        "welfare scheme", "kalaignar", "magalir urimai", "da hike", "salary", "police",
        "தலைமைச் செயலகம்", "அமைச்சரவை", "அரசாணை", "முதலமைச்சர்", "திட்டம்"
    ],
    "Political Parties": [
        "alliance", "general council", "executive committee", "party meeting",
        "public meeting", "conference", "cadre", "கூட்டணி", "பொதுக்குழு", "செயற்குழு", "மாநாடு"
    ],
    "Assembly, Courts & Policy": [
        "assembly", "speaker", "madras high court", "supreme court", "bill", "plea",
        "governor", "election commission", "சட்டப்பேரவை", "உயர் நீதிமன்றம்", "ஆளுநர்"
    ],
    "Elections": [
        "election", "by-election", "byelection", "constituency", "voter list", "electoral roll",
        "booth", "candidate", "தேர்தல்", "வாக்காளர்", "தொகுதி", "வேட்பாளர்"
    ],
    "Education & NEET": [
        "neet", "school education", "higher education", "university", "ugc",
        "board exam", "student", "நீட்", "கல்வி", "பல்கலைக்கழகம்", "பள்ளி"
    ],
    "Agriculture & Water": [
        "farmer", "cauvery", "mullaperiyar", "kuruvai", "samba", "paddy",
        "procurement", "delta", "reservoir", "விவசாயி", "காவிரி", "முல்லைப் பெரியாறு", "நெல்", "டெல்டா"
    ],
    "Public Protests & Labour": [
        "protest", "demonstration", "strike", "detained", "sanitation workers",
        "transport workers", "prison", "jail", "போராட்டம்", "ஆர்ப்பாட்டம்", "வேலைநிறுத்தம்"
    ],
    "Centre–State Relations": [
        "union government", "centre", "gst", "finance commission", "delimitation",
        "language policy", "india bloc", "மத்திய அரசு", "ஒன்றிய அரசு", "நிதி பகிர்வு", "தொகுதி மறுசீரமைப்பு"
    ],
    "Infrastructure & Economy": [
        "metro rail", "highway", "port", "industrial", "investment", "sipcot", "power cut",
        "tangedco", "tneb", "electricity", "மெட்ரோ", "மின்சாரம்", "தொழிற்சாலை", "முதலீடு"
    ],
}

TN_DISTRICTS = {
    "Ariyalur": ["ariyalur", "அரியலூர்"],
    "Chengalpattu": ["chengalpattu", "செங்கல்பட்டு"],
    "Chennai": ["chennai", "சென்னை"],
    "Coimbatore": ["coimbatore", "கோவை", "கோயம்புத்தூர்"],
    "Cuddalore": ["cuddalore", "கடலூர்"],
    "Dharmapuri": ["dharmapuri", "தர்மபுரி", "தருமபுரி"],
    "Dindigul": ["dindigul", "திண்டுக்கல்"],
    "Erode": ["erode", "ஈரோடு"],
    "Kallakurichi": ["kallakurichi", "கள்ளக்குறிச்சி"],
    "Kancheepuram": ["kancheepuram", "kanchipuram", "காஞ்சிபுரம்"],
    "Kanniyakumari": ["kanniyakumari", "kanyakumari", "கன்னியாகுமரி", "குமரி"],
    "Karur": ["karur", "கரூர்"],
    "Krishnagiri": ["krishnagiri", "கிருஷ்ணகிரி"],
    "Madurai": ["madurai", "மதுரை"],
    "Mayiladuthurai": ["mayiladuthurai", "மயிலாடுதுறை"],
    "Nagapattinam": ["nagapattinam", "நாகப்பட்டினம்", "நாகை"],
    "Namakkal": ["namakkal", "நாமக்கல்"],
    "Nilgiris": ["nilgiris", "ooty", "udhagamandalam", "நீலகிரி", "ஊட்டி"],
    "Perambalur": ["perambalur", "பெரம்பலூர்"],
    "Pudukkottai": ["pudukkottai", "புதுக்கோட்டை"],
    "Ramanathapuram": ["ramanathapuram", "ராமநாதபுரம்", "இராமநாதபுரம்"],
    "Ranipet": ["ranipet", "ராணிப்பேட்டை"],
    "Salem": ["salem", "சேலம்"],
    "Sivaganga": ["sivaganga", "சிவகங்கை"],
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
    "tamil nadu", "tamilnadu", "chennai", "assembly", "minister", "collector",
    "government", "policy", "court", "party", "election", "scheme",
    "தமிழ்நாடு", "தமிழகம்", "அரசு", "அமைச்சர்", "முதலமைச்சர்", "மாவட்டம்", "நீதிமன்றம்"
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

    # If triggered manually > 30 mins after scheduled time, capture latest 12 hours up to now
    if target_date_str is None and (now_ist - end_dt).total_seconds() > 1800:
        end_dt = now_ist
        start_dt = now_ist - timedelta(hours=12)

    date_str = scheduled_dt.strftime("%Y-%m-%d")
    human_date = scheduled_dt.strftime("%-d %B %Y") if os.name != "nt" else scheduled_dt.strftime("%d %B %Y").lstrip("0")
    edition_id = f"{date_str}-{edition_type}"

    return {
        "edition_id": edition_id,
        "date": date_str,
        "edition_type": edition_type,
        "title": f"Tamil Nadu Politics – {label} – {human_date}",
        "start_dt": start_dt,
        "end_dt": end_dt,
        "scheduled_dt": scheduled_dt,
        "coverage_start_ist": start_dt.isoformat(),
        "coverage_end_ist": end_dt.isoformat(),
        "scheduled_time_ist": scheduled_dt.isoformat(),
        "human_window": f"{start_dt.strftime('%d %b %Y, %I:%M %p IST')} – {end_dt.strftime('%d %b %Y, %I:%M %p IST')}",
    }


def sanitize_untrusted_text(text: str, max_length: int = 650) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    cleaned = re.split(
        r"(?:WATCH\s+LIVE|Follow\s+US|Subscribe\s+to|ID_[A-Z0-9]+|https?://\S+)",
        cleaned,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.sub(r"[👉🔴📺▶️⚡🔔]+", " ", cleaned)
    cleaned = re.sub(r"^(?:JUST\s+NOW|BREAKING\s+NEWS|\d+\s*-\s*)\s*[\|:\-–—]?\s*", "", cleaned, flags=re.IGNORECASE)

    if cleaned.count("|") >= 2:
        parts = [p.strip() for p in cleaned.split("|") if len(p.strip()) > 3]
        cleaned = " — ".join(parts[:2]) if parts else cleaned

    cleaned = re.sub(r"(\|\s*){1,}", " ", cleaned)
    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[REDACTED_INSTRUCTION]", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" |-–—:")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(" ", 1)[0] + "..."
    return cleaned


def has_tamil_script(text: str) -> bool:
    return bool(text and TAMIL_UNICODE_RE.search(text))


def translate_tamil_to_english(text: str) -> str:
    """Translate any Tamil or mixed Tamil-English text into 100% Pure English."""
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