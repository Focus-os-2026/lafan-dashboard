from flask import Flask, jsonify, send_from_directory
from google.cloud import bigquery
import os
import datetime
import random

app = Flask(__name__)

# Initialize BigQuery client
bq_client = None
try:
    # BigQuery Client automatically uses GCP Application Default Credentials (ADC)
    bq_client = bigquery.Client()
except Exception as e:
    print(f"Warning: Could not initialize BigQuery client locally: {e}")

@app.route('/')
def index():
    return send_from_directory('.', 'lafan.dashboard.html')

@app.route('/<path:path>')
def send_static(path):
    if os.path.exists(path) and not os.path.isdir(path):
        return send_from_directory('.', path)
    return "Not Found", 404

def get_mock_analytics():
    # Helper to generate realistic daily trends for 30 days
    today = datetime.date.today()
    daily_trends = []
    
    # Keep random seed stable or slight variations for a realistic look
    random.seed(42)
    
    for i in range(29, -1, -1):
        day = today - datetime.timedelta(days=i)
        visitors = random.randint(70, 160)
        pageviews = int(visitors * random.uniform(2.1, 3.4))
        clicks = int(visitors * random.uniform(0.4, 0.95))
        
        daily_trends.append({
            "day": str(day),
            "visitors": visitors,
            "pageviews": pageviews,
            "clicks": clicks
        })
        
    # Set today's stats based on the last element
    today_stats = daily_trends[-1]
    
    return {
        "summary": {
            "visitors_today": today_stats["visitors"],
            "pageviews_today": today_stats["pageviews"],
            "clicks_today": today_stats["clicks"]
        },
        "top_buttons": [
            {"label": "ซื้อบัตรคอนเสิร์ต (LinkHub Main)", "clicks": int(today_stats["clicks"] * 0.55)},
            {"label": "สอบถามเพิ่มเติมทาง Line", "clicks": int(today_stats["clicks"] * 0.30)},
            {"label": "ดูแผนที่จัดงาน (Google Maps)", "clicks": int(today_stats["clicks"] * 0.12)},
            {"label": "รายละเอียดศิลปิน", "clicks": int(today_stats["clicks"] * 0.03)}
        ],
        "daily_trends": daily_trends,
        "funnel": {
            "visitors": today_stats["visitors"],
            "clicked_buy": int(today_stats["visitors"] * random.uniform(0.45, 0.58)),
            "click_through_rate": 0.52
        },
        "is_mock": True
    }

@app.route('/api/analytics')
def get_analytics():
    # If BigQuery client isn't available or fails, seamlessly fall back to mock data
    if not bq_client:
        return jsonify(get_mock_analytics())
        
    try:
        # Query 1: Summary Cards
        summary_query = """
        SELECT
          COUNT(DISTINCT IF(type='pageview', visitor_id, NULL)) AS visitors_today,
          COUNTIF(type='pageview')                              AS pageviews_today,
          COUNTIF(type='click')                                 AS clicks_today
        FROM `fgs-link-manager.fgs_analytics.events`
        WHERE project='lafan' AND visitor_id!='curltest'
          AND DATE(event_time,'Asia/Bangkok') = CURRENT_DATE('Asia/Bangkok');
        """
        summary_job = bq_client.query(summary_query)
        summary_res = list(summary_job.result())
        
        summary_data = {
            "visitors_today": 0,
            "pageviews_today": 0,
            "clicks_today": 0
        }
        if summary_res:
            row = summary_res[0]
            summary_data = {
                "visitors_today": row.visitors_today or 0,
                "pageviews_today": row.pageviews_today or 0,
                "clicks_today": row.clicks_today or 0
            }

        # Query 2: Top Buttons Clicked
        top_buttons_query = """
        SELECT label, COUNT(*) AS clicks
        FROM `fgs-link-manager.fgs_analytics.events`
        WHERE project='lafan' AND type='click' AND visitor_id!='curltest'
          AND DATE(event_time,'Asia/Bangkok') = CURRENT_DATE('Asia/Bangkok')
        GROUP BY label
        ORDER BY clicks DESC;
        """
        top_job = bq_client.query(top_buttons_query)
        top_res = list(top_job.result())
        top_buttons = [{"label": row.label or "Unlabelled", "clicks": row.clicks or 0} for row in top_res]

        # Query 3: Daily Trends (30 Days)
        trends_query = """
        SELECT
          DATE(event_time,'Asia/Bangkok')                     AS day,
          COUNT(DISTINCT IF(type='pageview',visitor_id,NULL)) AS visitors,
          COUNTIF(type='pageview')                            AS pageviews,
          COUNTIF(type='click')                               AS clicks
        FROM `fgs-link-manager.fgs_analytics.events`
        WHERE project='lafan' AND visitor_id!='curltest'
          AND event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        GROUP BY day
        ORDER BY day;
        """
        trends_job = bq_client.query(trends_query)
        trends_res = list(trends_job.result())
        daily_trends = [{
            "day": str(row.day),
            "visitors": row.visitors or 0,
            "pageviews": row.pageviews or 0,
            "clicks": row.clicks or 0
        } for row in trends_res]

        # Query 4: Funnel (Visitors -> Clicked Buy)
        funnel_query = """
        SELECT
          COUNT(DISTINCT IF(type='pageview', visitor_id, NULL)) AS visitors,
          COUNT(DISTINCT IF(type='click' AND LOWER(label) LIKE '%บัตร%', visitor_id, NULL)) AS clicked_buy,
          SAFE_DIVIDE(
            COUNT(DISTINCT IF(type='click' AND LOWER(label) LIKE '%บัตร%', visitor_id, NULL)),
            COUNT(DISTINCT IF(type='pageview', visitor_id, NULL))
          ) AS click_through_rate
        FROM `fgs-link-manager.fgs_analytics.events`
        WHERE project='lafan' AND visitor_id!='curltest'
          AND DATE(event_time,'Asia/Bangkok') = CURRENT_DATE('Asia/Bangkok');
        """
        funnel_job = bq_client.query(funnel_query)
        funnel_res = list(funnel_job.result())
        funnel_data = {
            "visitors": 0,
            "clicked_buy": 0,
            "click_through_rate": 0.0
        }
        if funnel_res:
            row = funnel_res[0]
            funnel_data = {
                "visitors": row.visitors or 0,
                "clicked_buy": row.clicked_buy or 0,
                "click_through_rate": float(row.click_through_rate or 0.0)
            }

        return jsonify({
            "summary": summary_data,
            "top_buttons": top_buttons,
            "daily_trends": daily_trends,
            "funnel": funnel_data,
            "is_mock": False
        })
    except Exception as e:
        print(f"Error querying BigQuery, falling back to mock: {e}")
        # Return mock data as a fallback to keep the app working offline or before IAM roles take effect
        mock_data = get_mock_analytics()
        mock_data["bq_error"] = str(e)
        return jsonify(mock_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
