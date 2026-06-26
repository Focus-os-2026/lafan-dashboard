# FGS Analytics → Dashboard Integration (สำหรับทีม Dashboard)

เอกสารนี้ส่งให้ผู้พัฒนา **lafan-dashboard** เพื่อนำสถิติจาก LinkHub (คนเข้า/คลิก) มาแสดงบน dashboard เดียวกับยอดขายบัตร

---

## 1. ข้อมูลอยู่ที่ไหน

ทุก event (pageview / click) จากเว็บ FGS ถูกเก็บใน **BigQuery**:

```
Project : fgs-link-manager
Dataset : fgs_analytics
Table   : events   (partition by DATE(event_time))
```

> เก็บแบบ real-time ผ่าน collector service (`fgs-collector` บน Cloud Run) — ทุกครั้งที่มีคนเข้า/คลิกใน LinkHub จะมีแถวเพิ่มทันที

### โครงสร้างตาราง `events`
| field | type | ความหมาย |
|---|---|---|
| `event_time` | TIMESTAMP | เวลาเกิด (UTC) |
| `site` | STRING | เว็บต้นทาง เช่น `linkhub` |
| `project` | STRING | slug เช่น `lafan` |
| `type` | STRING | `pageview` หรือ `click` |
| `label` | STRING | ชื่อปุ่ม (เฉพาะ click) |
| `url` | STRING | ลิงก์ปลายทาง (เฉพาะ click) |
| `path`, `referrer` | STRING | path หน้า / มาจากไหน |
| `visitor_id` | STRING | id ผู้ชม (ใช้นับ unique) |
| `session_id` | STRING | id session |
| `user_agent`, `country` | STRING | อุปกรณ์ / ประเทศ |

---

## 2. ขอสิทธิ์อ่านข้าม project (ทำครั้งเดียว)

dashboard อยู่คนละ GCP project — ต้องให้ **service account ของ dashboard** อ่าน BigQuery ใน `fgs-link-manager` ได้

**ฝั่งทีม dashboard:** แจ้ง service account ที่ dashboard รันอยู่ (เช่น `xxxxxxxx-compute@developer.gserviceaccount.com`)
ดูได้จาก Cloud Run → service dashboard → tab "Security" → Service account

**ฝั่ง Bo (เจ้าของ fgs-link-manager):** รัน 2 คำสั่งนี้ (แทน `<DASHBOARD_SA>` ด้วยค่าที่ได้):
```bash
gcloud projects add-iam-policy-binding fgs-link-manager --member="serviceAccount:<DASHBOARD_SA>" --role="roles/bigquery.dataViewer"
gcloud projects add-iam-policy-binding fgs-link-manager --member="serviceAccount:<DASHBOARD_SA>" --role="roles/bigquery.jobUser"
```

หลังจากนี้ dashboard query ตาราง `fgs-link-manager.fgs_analytics.events` ได้เลย (ระบุชื่อเต็มแบบนี้ในทุก query)

---

## 3. SQL พร้อมใช้ (ทำเป็น widget ได้เลย)

> timezone ใช้ `Asia/Bangkok` ให้ "วันนี้" ตรงเวลาไทย
> ตัด test data ออกด้วย `visitor_id != 'curltest'`

### 3.1 การ์ดสรุป — คนเข้าวันนี้ / เพจวิว / คลิก
```sql
SELECT
  COUNT(DISTINCT IF(type='pageview', visitor_id, NULL)) AS visitors_today,
  COUNTIF(type='pageview')                              AS pageviews_today,
  COUNTIF(type='click')                                 AS clicks_today
FROM `fgs-link-manager.fgs_analytics.events`
WHERE project='lafan' AND visitor_id!='curltest'
  AND DATE(event_time,'Asia/Bangkok') = CURRENT_DATE('Asia/Bangkok');
```

### 3.2 ตาราง/กราฟแท่ง — ปุ่มไหนถูกคลิกบ่อยสุด (วันนี้)
```sql
SELECT label, COUNT(*) AS clicks
FROM `fgs-link-manager.fgs_analytics.events`
WHERE project='lafan' AND type='click' AND visitor_id!='curltest'
  AND DATE(event_time,'Asia/Bangkok') = CURRENT_DATE('Asia/Bangkok')
GROUP BY label
ORDER BY clicks DESC;
```

### 3.3 กราฟเส้น — เทรนด์รายวัน 30 วัน
```sql
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
```

### 3.4 ⭐ Funnel — เข้าหน้า → กดปุ่มซื้อบัตร (ของเด็ด)
```sql
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
```
> **ต่อยอด:** เอา `clicked_buy` ไปวางข้าง "ยอดขายบัตรจริง" ที่ dashboard มีอยู่แล้ว = เห็น funnel ครบ
> **คนเข้า → กดซื้อ → ซื้อจริง** วัดประสิทธิภาพหน้า LinkHub และแคมเปญได้เลย

---

## 4. หมายเหตุ
- ข้อมูลเป็น real-time (streaming insert) — query เห็นภายในไม่กี่วินาทีหลังเกิด event
- ค่าใช้จ่าย: query ฟรี 1TB แรก/เดือน — ระดับนี้แทบ 0 บาท
- ถ้าจะให้ dashboard เบาลง อาจทำ scheduled query สรุปเป็นตาราง summary รายวันก็ได้ (optional)
- เพิ่มเว็บอื่นในอนาคต: ข้อมูลจะมาที่ตารางเดียวกัน กรองด้วยคอลัมน์ `site` / `project`

---

## 5. ติดต่อ
ระบบ collector + schema ออกแบบไว้แล้ว (โดย Bo + Claude) — เอกสารเต็มที่ `fgs-analytics/README.md`
ถ้าต้องการปรับ field เพิ่ม หรืออยากได้ summary table สำเร็จรูป แจ้ง Bo ได้
