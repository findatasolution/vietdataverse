"""
CHAT-01 — MVP "Chat với dữ liệu VN".

POST /api/v1/chat
  Body: {"message": "...", "session_id": "...", "history": [...]}
  Auth: optional Bearer JWT (logged-in users get higher rate limit)

Rate limit:
  Anonymous: 5 messages / hour / IP
  Logged-in free: 20 messages / hour
  Premium: unlimited

Strategy (no tool-calling for MVP):
  1. Detect which data categories the question needs
  2. Pre-fetch that data from our own API (localhost)
  3. Build context: system prompt + live data + knowledge pack snippets
  4. Call Anthropic claude-sonnet-4-6
  5. Return response + sources used
"""

import json
import logging
import os
import time
from collections import defaultdict
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

_GEMINI_KEY    = os.getenv("GEMINI_API_KEY", "")
_GEMINI_MODEL  = "gemini-2.0-flash"
_API_SELF_BASE = os.getenv("API_SELF_BASE", "https://api.vietdataverse.online/api/v1")

# ── Rate limiting (in-memory, resets on restart) ──────────────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)
_ANON_LIMIT  = 5   # per hour
_FREE_LIMIT  = 20
_WINDOW_SECS = 3600

def _check_rate(key: str, limit: int) -> bool:
    now = time.time()
    hits = [t for t in _rate_store[key] if now - t < _WINDOW_SECS]
    _rate_store[key] = hits
    if len(hits) >= limit:
        return False
    _rate_store[key].append(now)
    return True


# ── Data fetcher ──────────────────────────────────────────────────────────────

async def _fetch_data(endpoint: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{_API_SELF_BASE}/{endpoint}")
            if r.status_code == 200:
                body = r.json()
                return body.get("data", [])[:10]  # cap at 10 rows for context size
    except Exception as e:
        logger.warning("Data fetch failed: %s — %s", endpoint, e)
    return []


def _detect_topics(message: str) -> list[str]:
    """Keyword detection to decide which data to pre-fetch."""
    msg = message.lower()
    topics = []
    if any(w in msg for w in ["vàng", "gold", "sjc", "doji", "pnj", "btmc"]):
        topics.append("gold")
    if any(w in msg for w in ["bạc", "silver"]):
        topics.append("silver")
    if any(w in msg for w in ["tỷ giá", "usd", "dollar", "đô", "ngoại tệ", "vcb", "exchange"]):
        topics.append("sbv-rate")
    if any(w in msg for w in ["tiết kiệm", "lãi suất", "gửi tiền", "kỳ hạn", "deposit", "acb", "saving"]):
        topics.append("termdepo")
    if any(w in msg for w in ["cpi", "lạm phát", "inflation", "giá cả"]):
        topics.append("macro/cpi")
    if any(w in msg for w in ["nasdaq", "sp500", "s&p", "chứng khoán mỹ", "global"]):
        topics.append("global?symbol=%5EIXIC")
    if any(w in msg for w in ["cổ phiếu", "vn30", "vn-index", "chứng khoán", "vcb", "tcb", "stock"]):
        topics.append("vn30_hint")  # can't fetch without ticker
    if not topics:
        topics = ["gold", "sbv-rate", "termdepo"]  # default context
    return topics


def _format_data_context(topic: str, rows: list[dict]) -> str:
    if not rows:
        return ""
    if topic == "gold":
        r = rows[0]
        return f"Giá vàng mới nhất ({r.get('date','')}): Mua {r.get('buy_price',0):,.0f} ₫ / Bán {r.get('sell_price',0):,.0f} ₫/lượng (DOJI HN)"
    if topic == "silver":
        r = rows[0]
        return f"Giá bạc mới nhất ({r.get('date','')}): {r.get('sell_price',0):,.0f} ₫/lượng"
    if topic == "sbv-rate":
        r = rows[0]
        return f"Tỷ giá USD/VND ({r.get('date','')}): VCB mua {r.get('vcb_buy',0):,.0f} / bán {r.get('vcb_sell',0):,.0f}"
    if topic == "termdepo":
        r = rows[0]
        parts = []
        for k, label in [("term_1m","1T"),("term_3m","3T"),("term_6m","6T"),("term_12m","12T"),("term_24m","24T")]:
            if r.get(k): parts.append(f"{label}: {r[k]:.2f}%")
        return f"Lãi suất tiết kiệm ACB ({r.get('date','')}): {' | '.join(parts)}"
    if topic == "macro/cpi":
        r = rows[0]
        return f"CPI Việt Nam mới nhất ({r.get('period','')}): {r.get('cpi_yoy',0):.2f}% (YoY)"
    if "IXIC" in topic or "global" in topic:
        r = rows[0]
        return f"Nasdaq ({r.get('date','')}): {r.get('close',0):,.2f} điểm"
    return ""


_SYSTEM_PROMPT = """Bạn là trợ lý phân tích tài chính Việt Nam của Viet Dataverse.

Chuyên môn của bạn:
- Kinh tế vĩ mô Việt Nam (CPI, lãi suất SBV, tỷ giá USD/VND, GDP)
- Thị trường vàng VN (SJC, DOJI, PNJ, BTMC — đặc biệt là premium SJC vs quốc tế)
- Lãi suất tiết kiệm ngân hàng (chu kỳ lãi suất, lãi suất thực, chiến lược gửi tiền)
- Cổ phiếu VN30 (phân tích ngành, sector rotation theo chu kỳ kinh tế)
- Hàng hóa quốc tế ảnh hưởng VN (dầu, thép, cà phê, gạo)
- Chính sách tiền tệ NHNN

Nguyên tắc trả lời:
1. Ưu tiên dùng dữ liệu thực tế được cung cấp (ghi rõ nguồn và ngày)
2. Phân tích ngắn gọn, có số liệu cụ thể, không mơ hồ
3. Nếu không có dữ liệu → nói rõ "Tôi không có dữ liệu cập nhật về X"
4. KHÔNG đưa ra khuyến nghị mua/bán tuyệt đối cho cổ phiếu/tài sản
5. KHÔNG dự báo giá cụ thể
6. Trả lời bằng tiếng Việt trừ khi user hỏi tiếng Anh
7. Nếu câu hỏi ngoài tài chính VN → từ chối nhẹ nhàng và redirect

Khi có dữ liệu thực tế, bắt đầu câu trả lời bằng số liệu đó, rồi mới phân tích."""


# ── Request / Response models ─────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: Optional[list[ChatMessage]] = []


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.post("/api/v1/chat")
async def chat(request: Request, body: ChatRequest):
    if not _GEMINI_KEY:
        raise HTTPException(status_code=503, detail="Chat service chưa được cấu hình. Thêm GEMINI_API_KEY vào env.")

    # Auth + rate limiting
    is_premium = False
    is_logged_in = False
    user_id_str = request.client.host if request.client else "anon"

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from middleware import authenticate_user
            await authenticate_user(request)
            user = getattr(request.state, "user", {})
            is_logged_in = True
            user_id_str = user.get("auth0_id", user_id_str)
            is_premium = user.get("user_level") in ("premium", "premium_developer", "admin")
        except Exception:
            pass  # treat as anonymous if auth fails

    rate_key = f"chat:{user_id_str}"
    if is_premium:
        pass  # no limit
    elif is_logged_in:
        if not _check_rate(rate_key, _FREE_LIMIT):
            raise HTTPException(status_code=429, detail="Đã đạt giới hạn 20 câu hỏi/giờ. Nâng cấp để dùng không giới hạn.")
    else:
        if not _check_rate(rate_key, _ANON_LIMIT):
            raise HTTPException(status_code=429, detail="Đã dùng hết 5 câu hỏi miễn phí/giờ. Đăng ký tài khoản để tiếp tục.")

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Tin nhắn không được để trống")
    if len(message) > 2000:
        raise HTTPException(status_code=422, detail="Tin nhắn quá dài (tối đa 2000 ký tự)")

    # Pre-fetch data
    topics = _detect_topics(message)
    data_lines = []
    sources_used = []

    for topic in topics:
        if topic == "vn30_hint":
            data_lines.append("Dữ liệu cổ phiếu VN30 có sẵn qua API — cần chỉ định ticker cụ thể (VCB, TCB, VHM, ...)")
            continue
        rows = await _fetch_data(topic)
        line = _format_data_context(topic, rows)
        if line:
            data_lines.append(line)
            sources_used.append(topic.split("?")[0])

    # Build messages for Anthropic
    system = _SYSTEM_PROMPT
    if data_lines:
        system += "\n\n--- DỮ LIỆU THỰC TẾ HÔM NAY ---\n" + "\n".join(data_lines)

    messages = []
    for h in (body.history or [])[-6:]:  # keep last 6 turns
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": message})

    # Call Gemini
    try:
        import google.generativeai as genai
        genai.configure(api_key=_GEMINI_KEY)
        model = genai.GenerativeModel(
            model_name=_GEMINI_MODEL,
            system_instruction=system,
        )
        # Convert to Gemini role format (user / model)
        gemini_msgs = [
            {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
            for m in messages
        ]
        resp = model.generate_content(
            gemini_msgs,
            generation_config={"max_output_tokens": 1024, "temperature": 0.4},
        )
        answer = resp.text
    except Exception as e:
        logger.error("Gemini API error: %s", e)
        raise HTTPException(status_code=502, detail="Dịch vụ AI tạm thời không khả dụng. Thử lại sau.")

    remaining = None
    if not is_premium:
        limit = _FREE_LIMIT if is_logged_in else _ANON_LIMIT
        used  = len(_rate_store.get(rate_key, []))
        remaining = max(0, limit - used)

    return Response(
        json.dumps({
            "success":   True,
            "answer":    answer,
            "sources":   sources_used,
            "remaining": remaining,
        }, ensure_ascii=False),
        media_type="application/json",
    )
