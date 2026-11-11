import os
import shutil
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import openpyxl

from importer import (
    get_db,
    init_db,
    load_config,
    save_config,
    sync_watch_folder,
    import_excel_file,
    recalculate_all_orders,
    DB_FILE
)
from importer_ads import (
    init_ads_table,
    import_ads_csv_file,
    sync_ads_watch_folder,
    update_ad_target_roas
)
from importer_transaksi import (
    init_transactions_table,
    import_balance_report_file,
    sync_transaksi_watch_folders
)

app = FastAPI(title="Shopee Bookkeeping & Profit Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

init_db()
init_ads_table()
init_transactions_table()

def init_expenses_table():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """)
        conn.commit()

init_expenses_table()

def build_filter_clauses(
    period: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    model: Optional[str] = None,
    bolt: Optional[str] = None,
    province: Optional[str] = None,
    city: Optional[str] = None,
    search: Optional[str] = None
):
    clauses = []
    params = []

    today = datetime.date.today().strftime("%Y-%m-%d")

    if period == "today":
        clauses.append("substr(order_created_at, 1, 10) = ?")
        params.append(today)
    elif period == "yesterday":
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        clauses.append("substr(order_created_at, 1, 10) = ?")
        params.append(yesterday)
    elif period == "7days":
        start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        clauses.append("substr(order_created_at, 1, 10) >= ?")
        params.append(start_date)
    elif period == "30days":
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        clauses.append("substr(order_created_at, 1, 10) >= ?")
        params.append(start_date)
    elif period == "custom" or (date_from or date_to):
        if date_from:
            clauses.append("substr(order_created_at, 1, 10) >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("substr(order_created_at, 1, 10) <= ?")
            params.append(date_to)

    if status and status.lower() != "all":
        clauses.append("order_status = ?")
        params.append(status)

    if model and model.lower() != "all":
        clauses.append("model_type = ?")
        params.append(model)

    if bolt is not None and bolt.lower() != "all" and bolt != "":
        clauses.append("has_bolt = ?")
        params.append(int(bolt))

    if province and province.lower() != "all":
        clauses.append("province = ?")
        params.append(province)

    if city and city.lower() != "all":
        clauses.append("city = ?")
        params.append(city)

    if search and search.strip():
        term = f"%{search.strip()}%"
        clauses.append("""(
            order_no LIKE ? OR
            tracking_no LIKE ? OR
            buyer_username LIKE ? OR
            recipient_name LIKE ? OR
            city LIKE ? OR
            province LIKE ? OR
            raw_address LIKE ? OR
            variation_name LIKE ?
        )""")
        params.extend([term] * 8)

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params

@app.get("/api/stats")
def get_stats(
    period: Optional[str] = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = "all",
    model: Optional[str] = "all",
    bolt: Optional[str] = "all",
    province: Optional[str] = "all",
    city: Optional[str] = "all",
    search: Optional[str] = None
):
    where_sql, params = build_filter_clauses(period, date_from, date_to, status, model, bolt, province, city, search)

    with get_db() as conn:
        query = f"""
        SELECT
            COUNT(DISTINCT order_no) as total_orders,
            COUNT(id) as total_items,
            COALESCE(SUM(qty), 0) as total_cover_qty,
            COALESCE(SUM(CASE WHEN has_bolt = 1 THEN qty ELSE 0 END), 0) as total_bolt_qty,
            COALESCE(SUM(CASE WHEN has_bolt = 0 THEN qty ELSE 0 END), 0) as total_tanpa_baut_qty,
            COALESCE(SUM(subtotal), 0) as total_omzet,
            COALESCE(SUM(shopee_admin_fee), 0) as total_admin_fee,
            COALESCE(SUM(shopee_process_fee), 0) as total_process_fee,
            COALESCE(SUM(shopee_gratis_ongkir_xtra), 0) as total_gratis_ongkir_xtra,
            COALESCE(SUM(shopee_promo_fee), 0) as total_promo_fee,
            COALESCE(SUM(shopee_pph22), 0) as total_pph22,
            COALESCE(SUM(total_shopee_deductions), 0) as total_shopee_deductions,
            COALESCE(SUM(net_payout), 0) as total_net_payout,
            COALESCE(SUM(total_hpp), 0) as total_hpp,
            COALESCE(SUM(total_hpp_cover), 0) as total_hpp_cover,
            COALESCE(SUM(total_hpp_bolt), 0) as total_hpp_bolt,
            COALESCE(SUM(profit), 0) as total_profit
        FROM orders
        {where_sql}
        """
        row = dict(conn.execute(query, params).fetchone())

        total_omzet = row["total_omzet"]
        total_profit = row["total_profit"]
        total_orders = row["total_orders"]

        row["avg_margin_pct"] = round((total_profit / total_omzet * 100), 2) if total_omzet > 0 else 0.0
        row["avg_profit_per_order"] = round(total_profit / total_orders, 2) if total_orders > 0 else 0.0

        status_query = f"SELECT order_status, COUNT(*) as cnt FROM orders {where_sql} GROUP BY order_status"
        status_rows = conn.execute(status_query, params).fetchall()
        row["status_breakdown"] = {r["order_status"]: r["cnt"] for r in status_rows if r["order_status"]}

        model_query = f"SELECT model_type, SUM(qty) as total_qty, SUM(profit) as total_profit FROM orders {where_sql} GROUP BY model_type"
        model_rows = conn.execute(model_query, params).fetchall()
        row["model_breakdown"] = [dict(r) for r in model_rows]

        bolt_query = f"SELECT has_bolt, SUM(qty) as total_qty, SUM(profit) as total_profit FROM orders {where_sql} GROUP BY has_bolt"
        bolt_rows = conn.execute(bolt_query, params).fetchall()
        row["bolt_breakdown"] = [
            {"label": "Dengan Baut (+2.000)" if r["has_bolt"] == 1 else "Tanpa Baut", "qty": r["total_qty"], "profit": r["total_profit"]}
            for r in bolt_rows
        ]

        prov_rows = conn.execute("SELECT DISTINCT province FROM orders WHERE province IS NOT NULL AND province != '' ORDER BY province").fetchall()
        row["available_provinces"] = [r["province"] for r in prov_rows]

    return row

@app.get("/api/orders")
def get_orders(
    period: Optional[str] = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = "all",
    model: Optional[str] = "all",
    bolt: Optional[str] = "all",
    province: Optional[str] = "all",
    city: Optional[str] = "all",
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    sort_by: str = "order_created_at",
    sort_order: str = "DESC"
):
    where_sql, params = build_filter_clauses(period, date_from, date_to, status, model, bolt, province, city, search)

    allowed_sort_cols = [
        "order_created_at", "order_no", "qty", "subtotal", "total_shopee_deductions",
        "net_payout", "total_hpp", "profit", "margin_pct", "order_status", "province", "city"
    ]
    if sort_by not in allowed_sort_cols:
        sort_by = "order_created_at"
    sort_order = "ASC" if sort_order.upper() == "ASC" else "DESC"

    offset = (page - 1) * limit

    with get_db() as conn:
        count_query = f"SELECT COUNT(*) as total FROM orders {where_sql}"
        total_count = conn.execute(count_query, params).fetchone()["total"]

        orders_query = f"""
        SELECT * FROM orders
        {where_sql}
        ORDER BY {sort_by} {sort_order}
        LIMIT ? OFFSET ?
        """
        rows = conn.execute(orders_query, params + [limit, offset]).fetchall()
        orders = [dict(r) for r in rows]

    return {
        "orders": orders,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1
    }

@app.get("/api/charts")
def get_charts(
    period: Optional[str] = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = "all",
    province: Optional[str] = "all"
):
    where_sql, params = build_filter_clauses(period, date_from, date_to, status, province=province)

    with get_db() as conn:
        timeline_query = f"""
        SELECT
            substr(order_created_at, 1, 10) as date,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as omzet,
            SUM(total_shopee_deductions) as deductions,
            SUM(net_payout) as net_payout,
            SUM(total_hpp) as hpp,
            SUM(profit) as profit
        FROM orders
        {where_sql}
        GROUP BY substr(order_created_at, 1, 10)
        ORDER BY date ASC
        """
        timeline_rows = [dict(r) for r in conn.execute(timeline_query, params).fetchall()]

        hourly_query = f"""
        SELECT
            substr(order_created_at, 12, 2) as hour,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as omzet,
            SUM(profit) as profit
        FROM orders
        {where_sql}
        WHERE order_created_at IS NOT NULL AND length(order_created_at) >= 13
        GROUP BY hour
        ORDER BY hour ASC
        """
        hourly_raw = {r["hour"]: dict(r) for r in conn.execute(hourly_query, params).fetchall()}
        hourly_slots = []
        best_hour_item = {"hour": "-", "total_qty": 0}
        for h in range(24):
            h_str = f"{h:02d}"
            item = hourly_raw.get(h_str, {"hour": h_str, "orders_count": 0, "total_qty": 0, "omzet": 0, "profit": 0})
            if item["total_qty"] > best_hour_item["total_qty"]:
                best_hour_item = item
            hourly_slots.append(item)

        dow_names = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
        dow_order = [1, 2, 3, 4, 5, 6, 0]
        
        dow_query = f"""
        SELECT
            strftime('%w', order_created_at) as dow,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as omzet,
            SUM(profit) as profit
        FROM orders
        {where_sql}
        WHERE order_created_at IS NOT NULL
        GROUP BY dow
        """
        dow_raw = {int(r["dow"]): dict(r) for r in conn.execute(dow_query, params).fetchall()}
        day_of_week_slots = []
        best_day_item = {"day_name": "-", "total_qty": 0}
        
        for idx in dow_order:
            name = dow_names[idx]
            item = dow_raw.get(idx, {"dow": str(idx), "orders_count": 0, "total_qty": 0, "omzet": 0, "profit": 0})
            item["day_name"] = name
            if item["total_qty"] > best_day_item["total_qty"]:
                best_day_item = item
            day_of_week_slots.append(item)

        month_query = f"""
        SELECT
            substr(order_created_at, 1, 7) as month,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as omzet,
            SUM(total_shopee_deductions) as deductions,
            SUM(net_payout) as net_payout,
            SUM(total_hpp) as hpp,
            SUM(profit) as profit
        FROM orders
        {where_sql}
        WHERE order_created_at IS NOT NULL AND length(order_created_at) >= 7
        GROUP BY month
        ORDER BY month ASC
        """
        month_rows = [dict(r) for r in conn.execute(month_query, params).fetchall()]
        
        month_names_id = {
            "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "Mei", "06": "Jun",
            "07": "Jul", "08": "Ags", "09": "Sep", "10": "Okt", "11": "Nov", "12": "Des"
        }
        for m in month_rows:
            parts = m["month"].split("-")
            if len(parts) == 2:
                m["label"] = f"{month_names_id.get(parts[1], parts[1])} {parts[0]}"
            else:
                m["label"] = m["month"]

        best_month_item = max(month_rows, key=lambda x: x["total_qty"]) if month_rows else {"label": "-", "total_qty": 0}

        city_query = f"""
        SELECT
            city,
            province,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as omzet,
            SUM(profit) as profit
        FROM orders
        {where_sql}
        WHERE city IS NOT NULL AND city != ''
        GROUP BY city
        ORDER BY total_qty DESC, omzet DESC
        LIMIT 10
        """
        city_rows = [dict(r) for r in conn.execute(city_query, params).fetchall()]
        best_city_item = city_rows[0] if city_rows else {"city": "-", "total_qty": 0}

        prov_query = f"""
        SELECT
            province,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as omzet,
            SUM(profit) as profit
        FROM orders
        {where_sql}
        WHERE province IS NOT NULL AND province != ''
        GROUP BY province
        ORDER BY total_qty DESC
        LIMIT 8
        """
        prov_rows = [dict(r) for r in conn.execute(prov_query, params).fetchall()]

        # Peringkat Produk Terlaris
        top_prod_query = f"""
        SELECT
            product_name,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as total_omzet,
            SUM(total_shopee_deductions) as total_deductions,
            SUM(net_payout) as total_net_payout,
            SUM(total_hpp) as total_hpp,
            SUM(profit) as total_profit,
            ROUND(SUM(profit) / NULLIF(SUM(subtotal), 0) * 100, 1) as margin_pct
        FROM orders
        {where_sql}
        GROUP BY product_name
        ORDER BY total_qty DESC, total_omzet DESC
        LIMIT 10
        """
        top_products = [dict(r) for r in conn.execute(top_prod_query, params).fetchall()]

        # Peringkat Varian Terlaris
        top_var_query = f"""
        SELECT
            product_name,
            variation_name,
            model_type,
            has_bolt,
            pack_type,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as total_omzet,
            SUM(profit) as total_profit,
            ROUND(SUM(profit) / NULLIF(SUM(subtotal), 0) * 100, 1) as margin_pct
        FROM orders
        {where_sql}
        GROUP BY product_name, variation_name
        ORDER BY total_qty DESC, total_omzet DESC
        LIMIT 15
        """
        top_variants = [dict(r) for r in conn.execute(top_var_query, params).fetchall()]

        # Model Breakdown (Model New vs Model Old)
        model_sum_query = f"""
        SELECT
            model_type,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as total_omzet,
            SUM(profit) as total_profit
        FROM orders
        {where_sql}
        GROUP BY model_type
        ORDER BY total_qty DESC
        """
        models_summary = [dict(r) for r in conn.execute(model_sum_query, params).fetchall()]

        # Bolt Breakdown (Dengan Baut vs Tanpa Baut)
        bolt_sum_query = f"""
        SELECT
            has_bolt,
            COUNT(DISTINCT order_no) as orders_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as total_omzet,
            SUM(profit) as total_profit
        FROM orders
        {where_sql}
        GROUP BY has_bolt
        ORDER BY total_qty DESC
        """
        bolts_summary = [dict(r) for r in conn.execute(bolt_sum_query, params).fetchall()]

    best_prod_item = top_products[0] if top_products else {"product_name": "-", "total_qty": 0}
    best_var_item = top_variants[0] if top_variants else {"variation_name": "-", "total_qty": 0}

    return {
        "timeline": timeline_rows,
        "hourly": hourly_slots,
        "days_of_week": day_of_week_slots,
        "monthly": month_rows,
        "cities": city_rows,
        "provinces": prov_rows,
        "top_products": top_products,
        "top_variants": top_variants,
        "models_summary": models_summary,
        "bolts_summary": bolts_summary,
        "best_insights": {
            "best_day": f"{best_day_item['day_name']} ({best_day_item['total_qty']} Unit)" if best_day_item['total_qty'] > 0 else "-",
            "best_hour": f"Pukul {best_hour_item['hour']}:00 WIB ({best_hour_item['total_qty']} Unit)" if best_hour_item['total_qty'] > 0 else "-",
            "best_month": f"{best_month_item.get('label', '-')} ({best_month_item['total_qty']} Unit)" if best_month_item['total_qty'] > 0 else "-",
            "best_city": f"{best_city_item['city']} ({best_city_item['total_qty']} Unit)" if best_city_item['total_qty'] > 0 else "-",
            "best_product": f"{best_prod_item['product_name'][:35]}... ({best_prod_item['total_qty']} Unit)" if best_prod_item['total_qty'] > 0 else "-",
            "best_variant": f"{best_var_item['variation_name']} ({best_var_item['total_qty']} Unit)" if best_var_item['total_qty'] > 0 else "-"
        }
    }

# ==================== SHOPEE ADS REST API ====================

@app.get("/api/ads/stats")
def get_ads_stats():
    init_ads_table()
    with get_db() as conn:
        q = """
        SELECT
            COUNT(id) as total_campaign_records,
            COUNT(DISTINCT product_id) as total_products,
            COUNT(DISTINCT period_raw) as total_periods,
            COALESCE(SUM(impressions), 0) as total_impressions,
            COALESCE(SUM(clicks), 0) as total_clicks,
            COALESCE(SUM(conversions), 0) as total_conversions,
            COALESCE(SUM(units_sold), 0) as total_units_sold,
            COALESCE(SUM(ad_gmv), 0) as total_ad_gmv,
            COALESCE(SUM(ad_spend), 0) as total_ad_spend
        FROM shopee_ads
        """
        row = dict(conn.execute(q).fetchone())

        total_gmv = row["total_ad_gmv"]
        total_spend = row["total_ad_spend"]
        total_clicks = row["total_clicks"]
        total_conversions = row["total_conversions"]
        total_impressions = row["total_impressions"]

        row["overall_roas"] = round(total_gmv / total_spend, 2) if total_spend > 0 else 0.0
        row["overall_acos_pct"] = round((total_spend / total_gmv * 100), 2) if total_gmv > 0 else 0.0
        row["overall_ctr_pct"] = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0.0
        row["overall_cpc"] = round(total_spend / total_clicks, 2) if total_clicks > 0 else 0.0
        row["overall_cpa"] = round(total_spend / total_conversions, 2) if total_conversions > 0 else 0.0

    return row

@app.get("/api/ads/history")
def get_ads_history(
    period: Optional[str] = "all",
    product_id: Optional[str] = "all",
    sort_by: str = "period_start",
    sort_order: str = "DESC"
):
    init_ads_table()
    clauses = []
    params = []

    if period and period != "all":
        clauses.append("period_raw = ?")
        params.append(period)

    if product_id and product_id != "all":
        clauses.append("product_id = ?")
        params.append(product_id)

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    allowed_cols = ["period_start", "ad_name", "units_sold", "ad_gmv", "ad_spend", "actual_roas", "target_roas", "acos_pct", "clicks"]
    if sort_by not in allowed_cols:
        sort_by = "period_start"
    sort_order = "ASC" if sort_order.upper() == "ASC" else "DESC"

    with get_db() as conn:
        q = f"""
        SELECT * FROM shopee_ads
        {where_sql}
        ORDER BY {sort_by} {sort_order}, id DESC
        """
        rows = [dict(r) for r in conn.execute(q, params).fetchall()]

        periods = [r["period_raw"] for r in conn.execute("SELECT DISTINCT period_raw FROM shopee_ads ORDER BY period_start DESC").fetchall()]
        products = [dict(r) for r in conn.execute("SELECT DISTINCT product_id, ad_name FROM shopee_ads").fetchall()]

    return {
        "records": rows,
        "available_periods": periods,
        "available_products": products
    }

@app.get("/api/ads/charts")
def get_ads_charts():
    init_ads_table()
    with get_db() as conn:
        # 1. Timeline per Period (Spend vs GMV vs ROAS)
        period_query = """
        SELECT
            period_raw,
            period_start,
            SUM(units_sold) as total_units,
            SUM(ad_gmv) as total_gmv,
            SUM(ad_spend) as total_spend,
            ROUND(SUM(ad_gmv) / NULLIF(SUM(ad_spend), 0), 2) as roas,
            ROUND(SUM(ad_spend) * 100.0 / NULLIF(SUM(ad_gmv), 0), 2) as acos_pct
        FROM shopee_ads
        GROUP BY period_raw
        ORDER BY period_start ASC
        """
        period_rows = [dict(r) for r in conn.execute(period_query).fetchall()]

        # 2. ROAS vs Sales Correlation (Group by ROAS range / campaigns)
        roas_query = """
        SELECT
            id,
            ad_name,
            period_raw,
            target_roas,
            actual_roas,
            units_sold,
            ad_gmv,
            ad_spend
        FROM shopee_ads
        ORDER BY actual_roas ASC
        """
        roas_rows = [dict(r) for r in conn.execute(roas_query).fetchall()]

        # 3. Product Performance Breakdown
        product_query = """
        SELECT
            product_id,
            ad_name,
            MAX(target_roas) as target_roas,
            SUM(units_sold) as total_units,
            SUM(ad_gmv) as total_gmv,
            SUM(ad_spend) as total_spend,
            ROUND(SUM(ad_gmv) / NULLIF(SUM(ad_spend), 0), 2) as avg_roas
        FROM shopee_ads
        GROUP BY product_id
        ORDER BY total_gmv DESC
        """
        product_rows = [dict(r) for r in conn.execute(product_query).fetchall()]

    return {
        "period_trends": period_rows,
        "roas_correlation": roas_rows,
        "product_performance": product_rows
    }

@app.post("/api/ads/sync")
def api_sync_ads(force: bool = True):
    res = sync_ads_watch_folder(force=force)
    return res

@app.post("/api/ads/target-roas")
def api_set_target_roas(data: dict):
    ad_id = data.get("id")
    product_id = data.get("product_id")
    target_roas = float(data.get("target_roas", 0))

    if product_id:
        with get_db() as conn:
            conn.execute("UPDATE shopee_ads SET target_roas = ? WHERE product_id = ?", (target_roas, str(product_id)))
            conn.commit()
        # Save to config.json
        cfg = load_config()
        if "product_target_roas" not in cfg:
            cfg["product_target_roas"] = {}
        cfg["product_target_roas"][str(product_id)] = target_roas
        save_config(cfg)
        return {"status": "success", "product_id": str(product_id), "target_roas": target_roas}

    if not ad_id:
        raise HTTPException(status_code=400, detail="Missing ad id or product_id")
    return update_ad_target_roas(ad_id, target_roas)

# ==================== GENERAL BOOKKEEPING & EXPENSES ====================

def build_expense_filter(period=None, date_from=None, date_to=None, category=None, search=None):
    clauses = []
    params = []
    today = datetime.date.today().strftime("%Y-%m-%d")

    if period == "today":
        clauses.append("expense_date = ?")
        params.append(today)
    elif period == "yesterday":
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        clauses.append("expense_date = ?")
        params.append(yesterday)
    elif period == "7days":
        start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        clauses.append("expense_date >= ?")
        params.append(start_date)
    elif period == "30days":
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        clauses.append("expense_date >= ?")
        params.append(start_date)
    elif period == "custom" or (date_from or date_to):
        if date_from:
            clauses.append("expense_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("expense_date <= ?")
            params.append(date_to)

    if category and category.lower() != "all":
        clauses.append("category = ?")
        params.append(category)

    if search and search.strip():
        term = f"%{search.strip()}%"
        clauses.append("(title LIKE ? OR notes LIKE ? OR category LIKE ?)")
        params.extend([term, term, term])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params

@app.get("/api/expenses")
def get_expenses(
    period: Optional[str] = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    category: Optional[str] = "all",
    search: Optional[str] = None
):
    init_expenses_table()
    where_sql, params = build_expense_filter(period, date_from, date_to, category, search)

    with get_db() as conn:
        q = f"SELECT * FROM expenses {where_sql} ORDER BY expense_date DESC, id DESC"
        rows = [dict(r) for r in conn.execute(q, params).fetchall()]

        total_amount = sum(r["amount"] for r in rows)

        # Breakdown per category
        cat_q = f"SELECT category, SUM(amount) as total_cat, COUNT(id) as count_cat FROM expenses {where_sql} GROUP BY category ORDER BY total_cat DESC"
        cat_rows = [dict(r) for r in conn.execute(cat_q, params).fetchall()]

        # All distinct categories
        all_cats_rows = conn.execute("SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL AND category != ''").fetchall()
        all_categories = [r["category"] for r in all_cats_rows]

    return {
        "expenses": rows,
        "total_count": len(rows),
        "total_amount": total_amount,
        "category_breakdown": cat_rows,
        "available_categories": all_categories
    }

@app.post("/api/expenses")
def add_expense(data: dict):
    init_expenses_table()
    expense_date = data.get("expense_date") or datetime.date.today().strftime("%Y-%m-%d")
    category = data.get("category", "Operasional").strip()
    title = data.get("title", "").strip()
    amount = float(data.get("amount", 0))
    notes = data.get("notes", "").strip()

    if not title:
        raise HTTPException(status_code=400, detail="Nama/deskripsi biaya harus diisi")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal biaya harus lebih besar dari 0")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cur = conn.execute("""
        INSERT INTO expenses (expense_date, category, title, amount, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (expense_date, category, title, amount, notes, now, now))
        conn.commit()
        new_id = cur.lastrowid

    return {"status": "success", "id": new_id, "message": "Biaya berhasil dicatat"}

@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: int, data: dict):
    init_expenses_table()
    expense_date = data.get("expense_date")
    category = data.get("category")
    title = data.get("title")
    amount = data.get("amount")
    notes = data.get("notes")

    updates = []
    params = []
    if expense_date is not None:
        updates.append("expense_date = ?")
        params.append(expense_date)
    if category is not None:
        updates.append("category = ?")
        params.append(category.strip())
    if title is not None:
        updates.append("title = ?")
        params.append(title.strip())
    if amount is not None:
        updates.append("amount = ?")
        params.append(float(amount))
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes.strip())

    if not updates:
        return {"status": "noop"}

    updates.append("updated_at = ?")
    params.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    params.append(expense_id)

    with get_db() as conn:
        conn.execute(f"UPDATE expenses SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    return {"status": "success", "id": expense_id, "message": "Biaya berhasil diperbarui"}

@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int):
    init_expenses_table()
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
    return {"status": "success", "id": expense_id, "message": "Biaya berhasil dihapus"}

@app.get("/api/bookkeeping/pnl")
def get_bookkeeping_pnl(
    period: Optional[str] = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    init_expenses_table()
    orders_where, orders_params = build_filter_clauses(period=period, date_from=date_from, date_to=date_to)
    exp_where, exp_params = build_expense_filter(period=period, date_from=date_from, date_to=date_to)

    with get_db() as conn:
        # 1. Orders financial summary
        orders_q = f"""
        SELECT
            COUNT(DISTINCT order_no) as total_orders,
            COALESCE(SUM(qty), 0) as total_qty,
            COALESCE(SUM(subtotal), 0) as total_omzet,
            COALESCE(SUM(shopee_admin_fee), 0) as admin_fee,
            COALESCE(SUM(shopee_process_fee), 0) as process_fee,
            COALESCE(SUM(shopee_gratis_ongkir_xtra), 0) as ongkir_xtra,
            COALESCE(SUM(shopee_promo_fee), 0) as promo_fee,
            COALESCE(SUM(shopee_pph22), 0) as pph22,
            COALESCE(SUM(total_shopee_deductions), 0) as total_deductions,
            COALESCE(SUM(net_payout), 0) as net_payout,
            COALESCE(SUM(total_hpp), 0) as total_hpp,
            COALESCE(SUM(profit), 0) as gross_profit
        FROM orders
        {orders_where}
        """
        o = dict(conn.execute(orders_q, orders_params).fetchone())

        # 2. Expenses summary
        exp_q = f"""
        SELECT
            COALESCE(SUM(amount), 0) as total_expenses,
            COUNT(id) as total_expense_count
        FROM expenses
        {exp_where}
        """
        e = dict(conn.execute(exp_q, exp_params).fetchone())

        # Category breakdown of expenses
        cat_q = f"""
        SELECT category, SUM(amount) as amount, COUNT(id) as count
        FROM expenses
        {exp_where}
        GROUP BY category
        ORDER BY amount DESC
        """
        categories = [dict(r) for r in conn.execute(cat_q, exp_params).fetchall()]

        # 3. Sold items & variations summary with net profit
        items_q = f"""
        SELECT
            product_name,
            variation_name,
            model_type,
            has_bolt,
            COUNT(DISTINCT order_no) as order_count,
            SUM(qty) as total_qty,
            SUM(subtotal) as total_omzet,
            SUM(total_shopee_deductions) as total_deductions,
            SUM(total_hpp) as total_hpp,
            SUM(profit) as total_net_profit,
            ROUND(SUM(profit) * 100.0 / NULLIF(SUM(subtotal), 0), 2) as profit_margin_pct
        FROM orders
        {orders_where}
        GROUP BY product_name, variation_name, model_type, has_bolt
        ORDER BY total_net_profit DESC, total_qty DESC
        """
        sold_items = [dict(r) for r in conn.execute(items_q, orders_params).fetchall()]

        # 4. Sold order transactions list with net profit
        tx_q = f"""
        SELECT
            order_no,
            order_created_at,
            product_name,
            variation_name,
            model_type,
            has_bolt,
            qty,
            price_unit,
            subtotal,
            total_shopee_deductions,
            total_hpp,
            profit as net_profit,
            margin_pct,
            city,
            province,
            order_status
        FROM orders
        {orders_where}
        ORDER BY order_created_at DESC, id DESC
        """
        sold_transactions = [dict(r) for r in conn.execute(tx_q, orders_params).fetchall()]

        # Monthly timeline comparison (Omzet vs Shopee Fees vs HPP vs Biaya Tambahan vs Laba Bersih Akhir)
        month_q = """
        SELECT
            substr(expense_date, 1, 7) as month,
            SUM(amount) as total_month_expenses
        FROM expenses
        GROUP BY month
        """
        exp_months = {r["month"]: r["total_month_expenses"] for r in conn.execute(month_q).fetchall()}

    total_omzet = o["total_omzet"]
    gross_profit = o["gross_profit"]
    total_expenses = e["total_expenses"]
    net_business_profit = gross_profit - total_expenses
    net_business_margin_pct = round((net_business_profit / total_omzet * 100), 2) if total_omzet > 0 else 0.0

    return {
        "sales": o,
        "expenses": {
            "total_expenses": total_expenses,
            "total_count": e["total_expense_count"],
            "categories": categories
        },
        "pnl": {
            "total_omzet": total_omzet,
            "total_deductions": o["total_deductions"],
            "net_payout": o["net_payout"],
            "total_hpp": o["total_hpp"],
            "gross_profit": gross_profit,
            "gross_margin_pct": round((gross_profit / total_omzet * 100), 2) if total_omzet > 0 else 0.0,
            "total_extra_expenses": total_expenses,
            "net_business_profit": net_business_profit,
            "net_business_margin_pct": net_business_margin_pct
        },
        "sold_items": sold_items,
        "sold_transactions": sold_transactions
    }

# ==============================================================

@app.post("/api/import/sync")
def api_sync(force: bool = False):
    res_orders = sync_watch_folder(force=force)
    res_ads = sync_ads_watch_folder(force=force)
    res_tx = sync_transaksi_watch_folders(force=force)
    return {
        "status": "success",
        "orders": res_orders,
        "ads": res_ads,
        "transactions": res_tx
    }

@app.post("/api/import/upload")
async def api_upload(file: UploadFile = File(...)):
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".xlsx") or filename_lower.endswith(".xls") or filename_lower.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Hanya file Excel (.xlsx / .xls) atau CSV iklan (.csv) yang diperbolehkan.")

    save_path = UPLOADS_DIR / file.filename
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if filename_lower.endswith(".csv") or "iklan" in filename_lower:
        res = import_ads_csv_file(save_path)
    elif "balance" in filename_lower or "transaksi" in filename_lower or "mutasi" in filename_lower:
        res = import_balance_report_file(save_path)
    else:
        res = import_excel_file(save_path)
    return res

@app.get("/api/settings")
def api_get_settings():
    return load_config()

@app.post("/api/settings")
def api_update_settings(data: dict):
    cfg = load_config()
    allowed_keys = [
        "hpp_cover", "hpp_bolt", "extra_bubble_cost",
        "shopee_admin_fee_pct", "shopee_process_fee_flat",
        "shopee_gratis_ongkir_xtra_pct", "shopee_promo_auto_topup_pct",
        "shopee_pph22_pct", "watch_folder", "watch_folder_iklan"
    ]
    for k in allowed_keys:
        if k in data:
            cfg[k] = data[k]
    save_config(cfg)
    recalc_res = recalculate_all_orders()
    return {"status": "success", "config": cfg, "recalculate": recalc_res}

@app.get("/api/export")
def api_export(
    period: Optional[str] = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = "all",
    model: Optional[str] = "all",
    bolt: Optional[str] = "all"
):
    where_sql, params = build_filter_clauses(period, date_from, date_to, status, model, bolt)

    with get_db() as conn:
        rows = conn.execute(f"SELECT * FROM orders {where_sql} ORDER BY order_created_at DESC", params).fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Laporan Pembukuan Shopee"

    headers = [
        "No. Pesanan", "Status Pesanan", "Waktu Pesanan (Jam:Menit)", "Waktu Pembayaran",
        "No. Resi", "Nama Produk", "Nama Variasi", "Model", "Ada Baut?", "Packing", "Qty",
        "Harga Satuan (Rp)", "Subtotal Pesanan (Rp)",
        "Biaya Admin Shopee (Rp)", "Biaya Proses Pesanan (Rp)", "Gratis Ongkir XTRA (Rp)",
        "Biaya Promosi / Iklan (Rp)", "PPh 22 (Rp)", "Total Potongan Shopee (Rp)",
        "Penghasilan Bersih Shopee (Rp)",
        "HPP Cover (Rp)", "HPP Baut (Rp)", "Total Modal HPP (Rp)",
        "Keuntungan Bersih Real (Rp)", "Margin Real (%)",
        "Metode Bayar", "Username Pembeli", "Penerima", "Kota/Kabupaten", "Provinsi", "Alamat Lengkap Pengiriman"
    ]
    ws.append(headers)

    for r in rows:
        ws.append([
            r["order_no"],
            r["order_status"],
            r["order_created_at"],
            r["order_paid_at"],
            r["tracking_no"],
            r["product_name"],
            r["variation_name"],
            r["model_type"],
            "Ya (+ Baut)" if r["has_bolt"] else "Tidak (Tanpa Baut)",
            r["pack_type"],
            r["qty"],
            r["price_unit"],
            r["subtotal"],
            r["shopee_admin_fee"],
            r["shopee_process_fee"],
            r["shopee_gratis_ongkir_xtra"],
            r["shopee_promo_fee"],
            r["shopee_pph22"],
            r["total_shopee_deductions"],
            r["net_payout"],
            r["total_hpp_cover"],
            r["total_hpp_bolt"],
            r["total_hpp"],
            r["profit"],
            round(r["margin_pct"], 2),
            r["payment_method"],
            r["buyer_username"],
            r["recipient_name"],
            r["city"],
            r["province"],
            r["raw_address"]
        ])

    # Sheet 2: Biaya Operasional / Pengeluaran Tambahan
    with get_db() as conn:
        exp_rows = conn.execute("SELECT * FROM expenses ORDER BY expense_date DESC").fetchall()

    ws_exp = wb.create_sheet(title="Biaya Operasional")
    ws_exp.append(["ID", "Tanggal", "Kategori", "Deskripsi / Nama Biaya", "Nominal (Rp)", "Catatan Tambahan", "Waktu Input"])
    for er in exp_rows:
        ws_exp.append([
            er["id"],
            er["expense_date"],
            er["category"],
            er["title"],
            er["amount"],
            er["notes"],
            er["created_at"]
        ])

    export_path = BASE_DIR / "laporan_pembukuan_shopee.xlsx"
    wb.save(export_path)

    return FileResponse(
        path=str(export_path),
        filename=f"Pembukuan_Shopee_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

SHOPEE_ADS_SELLER_URL = "https://seller.shopee.co.id/portal/marketing/pas/index?source_page_id=1&from=1793725200&to=1793811599&type=new_cpc_homepage&group=today&view_mode=classic"

def get_brave_profile_dir(profile_name="sdrisanggalih") -> str:
    local_state_file = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser/Local State"
    if local_state_file.exists():
        try:
            import json
            with open(local_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = data.get("profile", {}).get("info_cache", {})
            for folder, info in profiles.items():
                if info.get("name") == profile_name:
                    return folder
        except Exception:
            pass
    return "Profile 9"

@app.post("/api/open-shopee-seller")
def open_shopee_seller_brave():
    import subprocess
    try:
        brave_bin = Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")
        profile_dir = get_brave_profile_dir("sdrisanggalih")
        if brave_bin.exists():
            # Invoke Brave binary directly so Chromium internal IPC opens the exact profile window
            subprocess.Popen([
                str(brave_bin),
                f"--profile-directory={profile_dir}",
                SHOPEE_ADS_SELLER_URL
            ])
            subprocess.Popen(["open", "-a", "Brave Browser"])
            return {"status": "success", "message": f"Berhasil membuka Shopee Seller di Brave (Profile: sdrisanggalih)"}
        else:
            subprocess.Popen(["open", SHOPEE_ADS_SELLER_URL])
            return {"status": "success", "message": "Berhasil membuka Shopee Seller Ads di browser utama"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

if __name__ == "__main__":
    import uvicorn
    cfg = load_config()
    port = int(cfg.get("port", 8000))
    print(f"🚀 Membuka Server Pembukuan Shopee di http://127.0.0.1:{port}")
    uvicorn.run("server:app", host="127.0.0.1", port=port, reload=True)
