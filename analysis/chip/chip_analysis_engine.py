import json
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0"


def safe_int(value, default=0):
    try:
        text = str(value).replace(",", "").replace("+", "").strip()
        if text in ["", "-", "--", "None"]:
            return default
        return int(float(text))
    except Exception:
        return default


def request_json(url, timeout=15):
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
    )

    with urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="ignore")
        return json.loads(body)


def recent_dates(days=15):
    today = datetime.today()

    for offset in range(days):
        date = today - timedelta(days=offset)
        yield date.strftime("%Y%m%d")


def normalize_stock_id(stock_id):
    return str(stock_id).strip().zfill(4)


def find_stock_row(rows, stock_id):
    stock_id = normalize_stock_id(stock_id)

    for row in rows:
        if not row:
            continue

        code = str(row[0]).strip()

        if code == stock_id:
            return row

    return None


def fetch_institutional_result(stock_id):
    stock_id = normalize_stock_id(stock_id)

    for date in recent_dates():
        params = urlencode(
            {
                "date": date,
                "selectType": "ALLBUT0999",
                "response": "json",
            }
        )

        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?{params}"

        try:
            data = request_json(url)
            rows = data.get("data", [])
            row = find_stock_row(rows, stock_id)

            if not row:
                continue

            foreign = safe_int(row[4] if len(row) > 4 else 0)
            investment_trust = safe_int(row[10] if len(row) > 10 else 0)
            dealer = safe_int(row[11] if len(row) > 11 else 0)
            total = safe_int(row[18] if len(row) > 18 else 0)

            return {
                "status": "ok",
                "source": "TWSE",
                "date": date,
                "foreign": foreign,
                "investment_trust": investment_trust,
                "dealer": dealer,
                "total": total,
            }

        except Exception:
            continue

    return {
        "status": "missing",
        "source": "TWSE",
        "date": "",
        "foreign": 0,
        "investment_trust": 0,
        "dealer": 0,
        "total": 0,
    }


def fetch_institutional_history(stock_id, max_days=10):
    stock_id = normalize_stock_id(stock_id)
    history = []

    for date in recent_dates(20):
        if len(history) >= max_days:
            break

        params = urlencode(
            {
                "date": date,
                "selectType": "ALLBUT0999",
                "response": "json",
            }
        )

        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?{params}"

        try:
            data = request_json(url)
            rows = data.get("data", [])
            row = find_stock_row(rows, stock_id)

            if not row:
                continue

            foreign = safe_int(row[4] if len(row) > 4 else 0)
            investment_trust = safe_int(row[10] if len(row) > 10 else 0)
            dealer = safe_int(row[11] if len(row) > 11 else 0)
            total = safe_int(row[18] if len(row) > 18 else 0)

            history.append(
                {
                    "date": date,
                    "foreign": foreign,
                    "investment_trust": investment_trust,
                    "dealer": dealer,
                    "total": total,
                }
            )

        except Exception:
            continue

    return history


def calculate_direction_streak(history, field):
    if not history:
        return {
            "direction": "flat",
            "days": 0,
        }

    first_value = history[0].get(field, 0)

    if first_value > 0:
        direction = "buy"
    elif first_value < 0:
        direction = "sell"
    else:
        return {
            "direction": "flat",
            "days": 0,
        }

    days = 0

    for item in history:
        value = item.get(field, 0)

        if direction == "buy" and value > 0:
            days += 1
            continue

        if direction == "sell" and value < 0:
            days += 1
            continue

        break

    return {
        "direction": direction,
        "days": days,
    }


def fetch_margin_result(stock_id):
    stock_id = normalize_stock_id(stock_id)
    url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"

    try:
        data = request_json(url)

        for row in data:
            code = str(row.get("股票代號", "")).strip()

            if code != stock_id:
                continue

            margin_prev = safe_int(row.get("融資前日餘額"))
            margin_balance = safe_int(row.get("融資今日餘額"))

            short_prev = safe_int(row.get("融券前日餘額"))
            short_balance = safe_int(row.get("融券今日餘額"))

            margin_change = margin_balance - margin_prev
            short_change = short_balance - short_prev

            short_margin_ratio = 0

            if margin_balance > 0:
                short_margin_ratio = round(short_balance / margin_balance * 100, 2)

            return {
                "status": "ok",
                "source": "TWSE_OPENAPI",
                "date": "",
                "margin_balance": margin_balance,
                "margin_change": margin_change,
                "short_balance": short_balance,
                "short_change": short_change,
                "short_margin_ratio": short_margin_ratio,
            }

    except Exception:
        pass

    return {
        "status": "missing",
        "source": "TWSE_OPENAPI",
        "date": "",
        "margin_balance": 0,
        "margin_change": 0,
        "short_balance": 0,
        "short_change": 0,
        "short_margin_ratio": 0,
    }


def fetch_broker_top15_result(stock_id):
    return {
        "status": "pending",
        "source": "TWSE_BSR",
        "date": "",
        "buy_top15": [],
        "sell_top15": [],
        "buy_top15_net": 0,
        "sell_top15_net": 0,
        "note": "TWSE BSR 需要驗證碼，TOP15 暫不納入自動化",
    }


def judge_institutional_status(result):
    if result.get("status") != "ok":
        return "法人資料不足"

    foreign = result.get("foreign", 0)
    trust = result.get("investment_trust", 0)
    dealer = result.get("dealer", 0)
    total = result.get("total", 0)

    positive_count = sum(1 for value in [foreign, trust, dealer] if value > 0)
    negative_count = sum(1 for value in [foreign, trust, dealer] if value < 0)

    if total > 0 and positive_count >= 2:
        return "法人偏多"

    if total < 0 and negative_count >= 2:
        return "法人偏空"

    if foreign < 0 and trust > 0:
        return "外資賣、投信撐"

    if foreign > 0 and trust < 0:
        return "外資買、投信賣"

    return "法人分歧"


def judge_margin_status(result):
    if result.get("status") != "ok":
        return "資券資料不足"

    margin_change = result.get("margin_change", 0)
    short_change = result.get("short_change", 0)

    if margin_change > 0 and short_change < 0:
        return "融資增、融券減"

    if margin_change < 0 and short_change > 0:
        return "融資減、融券增"

    if margin_change > 0 and short_change > 0:
        return "資券同步增"

    if margin_change < 0 and short_change < 0:
        return "資券同步減"

    if margin_change > 0:
        return "融資增加"

    if margin_change < 0:
        return "融資減少"

    if short_change > 0:
        return "融券增加"

    if short_change < 0:
        return "融券減少"

    return "資券持平"


def judge_major_force_status(institutional_status, margin_status, broker_result, institutional_streaks):
    if broker_result.get("status") == "ok":
        buy_net = broker_result.get("buy_top15_net", 0)
        sell_net = broker_result.get("sell_top15_net", 0)

        if buy_net > sell_net * 1.3:
            return "主力偏多"

        if sell_net > buy_net * 1.3:
            return "主力偏空"

        return "主力分歧"

    total_streak = institutional_streaks.get("total", {})
    foreign_streak = institutional_streaks.get("foreign", {})
    trust_streak = institutional_streaks.get("investment_trust", {})

    if (
        total_streak.get("direction") == "buy"
        and total_streak.get("days", 0) >= 3
    ):
        return "法人連買"

    if (
        total_streak.get("direction") == "sell"
        and total_streak.get("days", 0) >= 3
    ):
        return "法人連賣"

    if (
        foreign_streak.get("direction") == "buy"
        and foreign_streak.get("days", 0) >= 3
        and "融資減" in margin_status
    ):
        return "籌碼沉澱"

    if (
        foreign_streak.get("direction") == "sell"
        and foreign_streak.get("days", 0) >= 3
        and "融資增" in margin_status
    ):
        return "籌碼偏空"

    if (
        trust_streak.get("direction") == "buy"
        and trust_streak.get("days", 0) >= 3
    ):
        return "投信偏多"

    if institutional_status == "法人偏多" and "融資減" in margin_status:
        return "籌碼偏多"

    if institutional_status == "法人偏空" and "融資增" in margin_status:
        return "籌碼偏空"

    if "外資賣" in institutional_status and "融資增" in margin_status:
        return "籌碼偏亂"

    return "主力資料不足"


def apply_streak_score(score, streak, buy_points, sell_points, min_days=2, max_days=5):
    direction = streak.get("direction")
    days = streak.get("days", 0)

    if days < min_days:
        return score

    weight = min(days, max_days)

    if direction == "buy":
        score += buy_points * weight

    elif direction == "sell":
        score -= sell_points * weight

    return score


def calculate_chip_score(institutional_result, margin_result, broker_result, institutional_streaks):
    score = 50

    if institutional_result.get("status") == "ok":
        foreign = institutional_result.get("foreign", 0)
        trust = institutional_result.get("investment_trust", 0)
        dealer = institutional_result.get("dealer", 0)
        total = institutional_result.get("total", 0)

        if total > 0:
            score += 4
        elif total < 0:
            score -= 4

        if foreign > 0:
            score += 5
        elif foreign < 0:
            score -= 5

        if trust > 0:
            score += 4
        elif trust < 0:
            score -= 4

        if dealer > 0:
            score += 1
        elif dealer < 0:
            score -= 1

    score = apply_streak_score(
        score,
        institutional_streaks.get("foreign", {}),
        buy_points=2,
        sell_points=2,
    )

    score = apply_streak_score(
        score,
        institutional_streaks.get("investment_trust", {}),
        buy_points=2,
        sell_points=2,
    )

    score = apply_streak_score(
        score,
        institutional_streaks.get("total", {}),
        buy_points=2,
        sell_points=2,
    )

    if margin_result.get("status") == "ok":
        margin_change = margin_result.get("margin_change", 0)
        short_change = margin_result.get("short_change", 0)

        if margin_change > 0:
            score -= 4
        elif margin_change < 0:
            score += 4

        if short_change > 0:
            score -= 2
        elif short_change < 0:
            score += 2

    if broker_result.get("status") == "ok":
        buy_net = broker_result.get("buy_top15_net", 0)
        sell_net = broker_result.get("sell_top15_net", 0)

        if buy_net > sell_net * 1.3:
            score += 8
        elif sell_net > buy_net * 1.3:
            score -= 8

    score = max(0, min(100, score))

    return int(score)


def build_institutional_result_from_history(history):
    if not history:
        return {
            "status": "missing",
            "source": "TWSE_HISTORY_FALLBACK",
            "date": "",
            "foreign": 0,
            "investment_trust": 0,
            "dealer": 0,
            "total": 0,
        }

    latest = history[0]

    return {
        "status": "ok",
        "source": "TWSE_HISTORY_FALLBACK",
        "date": latest.get("date", ""),
        "foreign": latest.get("foreign", 0),
        "investment_trust": latest.get("investment_trust", 0),
        "dealer": latest.get("dealer", 0),
        "total": latest.get("total", 0),
    }


def analyze_chip(stock_id):
    stock_id = normalize_stock_id(stock_id)

    institutional_history = fetch_institutional_history(stock_id)
    institutional_result = fetch_institutional_result(stock_id)

    if institutional_result.get("status") != "ok" and institutional_history:
        institutional_result = build_institutional_result_from_history(
            institutional_history
        )

    institutional_streaks = {
        "foreign": calculate_direction_streak(institutional_history, "foreign"),
        "investment_trust": calculate_direction_streak(institutional_history, "investment_trust"),
        "dealer": calculate_direction_streak(institutional_history, "dealer"),
        "total": calculate_direction_streak(institutional_history, "total"),
    }

    margin_result = fetch_margin_result(stock_id)
    broker_result = fetch_broker_top15_result(stock_id)

    institutional_status = judge_institutional_status(institutional_result)
    margin_status = judge_margin_status(margin_result)

    major_force_status = judge_major_force_status(
        institutional_status=institutional_status,
        margin_status=margin_status,
        broker_result=broker_result,
        institutional_streaks=institutional_streaks,
    )

    chip_score = calculate_chip_score(
        institutional_result=institutional_result,
        margin_result=margin_result,
        broker_result=broker_result,
        institutional_streaks=institutional_streaks,
    )

    return {
        "stock_id": stock_id,
        "institutional": institutional_result,
        "institutional_history": institutional_history,
        "institutional_streaks": institutional_streaks,
        "margin": margin_result,
        "broker_top15": broker_result,
        "institutional_status": institutional_status,
        "margin_status": margin_status,
        "major_force_status": major_force_status,
        "chip_score": chip_score,
    }
