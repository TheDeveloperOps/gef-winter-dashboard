# app2.py
"""
Single-file Flask app (patched)
- Reads Google Sheet or local Excel fallback.
- Uses 'Name' column as athlete display name (prefers it over '/athletes/...' path).
- Search filters by name and athlete id.
- Leaderboards have internal scroll boxes and sticky headers.
- Configure START DATE by env CHALLENGE_START (YYYY-MM-DD).
- Configure auto-refresh via AUTO_REFRESH_SECONDS env var (default 300).
"""

import os
import pytz
import json
import logging
from datetime import datetime, timedelta, date
import pytz
import pandas as pd
from flask import Flask, render_template_string, jsonify
from google.oauth2 import service_account
import gspread

# Config
SHEET_ID = os.environ.get(
    'SHEET_ID', '1PF9liQPShcqMPNBScmV1_V3kUFaZcmlIHy8TLM4AmJc')
LOCAL_XLSX_FALLBACK = '/mnt/data/GEF WINTER CHALLENGE.xlsx'
START_DATE_ENV = os.environ.get('CHALLENGE_START')
if START_DATE_ENV:
    try:
        START_DATE = datetime.strptime(START_DATE_ENV, '%Y-%m-%d').date()
    except Exception:
        START_DATE = date(2025, 11, 18)
else:
    START_DATE = date(2025, 11, 18)

TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Kolkata')
AUTO_REFRESH_SECONDS = int(os.environ.get('AUTO_REFRESH_SECONDS', '300'))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('gef_dashboard')

app = Flask(__name__)

# Safe template without f-string braces interfering with JS: insert interval later using .replace
TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Green Energy Fitness - Winter Challenge Tracker</title>
  <style>
    html,body{height:100%;margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial}
    body{background:linear-gradient(135deg,#051622,#08323d);color:#e6f7ee;padding:20px}
    .container{max-width:1200px;margin:0 auto}
    .card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:14px;padding:18px;margin:10px;box-shadow:0 12px 30px rgba(2,6,23,0.6)}
    .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
    .stat{padding:12px;border-radius:12px}
    .title{font-weight:700;font-size:18px;margin-bottom:6px;color:#c7f7da}
    .big{font-size:28px;font-weight:800}
    .leaderboard{
      margin-top:12px;
      max-height:360px;
      overflow:auto;
      padding-right:6px;
    }
    table{width:100%;border-collapse:collapse}
    thead th{
      position:sticky;
      top:0;
      background:rgba(2,6,23,0.6);
      z-index:2;
      padding:10px;
      color:#d9fff0;
    }
    th,td{padding:10px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.03)}
    th{font-weight:700}
    .pos1{background:linear-gradient(90deg,rgba(255,255,255,0.03),transparent);}
    .pos2{background:linear-gradient(90deg,rgba(255,255,255,0.02),transparent);}
    .pos3{background:linear-gradient(90deg,rgba(255,255,255,0.015),transparent);}
    .header-total{background:linear-gradient(90deg,#16a34a,#059669);border-radius:8px;padding:8px;color:white}
    .header-walk{background:linear-gradient(90deg,#10b981,#059669);border-radius:8px;padding:8px;color:white}
    .header-run{background:linear-gradient(90deg,#34d399,#059669);border-radius:8px;padding:8px;color:white}
    .header-ride{background:linear-gradient(90deg,#6ee7b7,#10b981);border-radius:8px;padding:8px;color:white}
    .header-consistent{background:linear-gradient(90deg,#86efac,#4ade80);border-radius:8px;padding:8px;color:#052e19}
    .badge{background:#052e19;color:#dfffe3;padding:4px 8px;border-radius:999px;font-weight:700;font-size:12px}
    .search{width:100%;padding:12px;border-radius:12px;border:0;margin-bottom:12px}
    .refresh-btn{position:fixed;right:20px;bottom:20px;background:#10b981;color:white;border:none;padding:14px;border-radius:999px;box-shadow:0 12px 30px rgba(16,185,129,0.18);cursor:pointer}
    .corner-day{position:fixed;right:26px;top:26px;background:linear-gradient(90deg,#34d399,#10b981);padding:18px;border-radius:12px;color:#053018;font-weight:800;box-shadow:0 10px 30px rgba(3,7,18,0.6);font-size:20px}
    .small{font-size:12px;color:#bfead0}
    @media (max-width:900px){.grid{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <div class="container">
    <h1 style="font-size:26px;margin:6px 0 12px">Green Energy Fitness — Winter Challenge</h1>

    <div class="card">
      <input id="search" class="search" placeholder="Search athlete by name or ID..." oninput="applySearch()">
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <div class="stat card" style="flex:1">
          <div class="title">Total Athletes</div>
          <div id="total-athletes" class="big">—</div>
        </div>
        <div class="stat card" style="flex:1">
          <div class="title">Days Running</div>
          <div id="days-running" class="big">—</div>
        </div>
        <div class="stat card" style="flex:1">
          <div class="title">Consistent Performers</div>
          <div id="consistent-count" class="big">—</div>
        </div>
        <div class="stat card" style="flex:1">
          <div class="title">Top Distance</div>
          <div id="top-distance" class="big">— km</div>
        </div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="header-total">Top Total Distance</div>
        <div id="leader-total" class="leaderboard"></div>
      </div>

      <div class="card">
        <div class="header-walk">Top Walkers (KM)</div>
        <div id="leader-walk" class="leaderboard"></div>
      </div>

      <div class="card">
        <div class="header-run">Top Runners (KM)</div>
        <div id="leader-run" class="leaderboard"></div>
      </div>

      <div class="card">
        <div class="header-ride">Top Riders (KM)</div>
        <div id="leader-ride" class="leaderboard"></div>
      </div>

      <div class="card" style="grid-column:1 / -1">
        <div class="header-consistent">ALL DAY PERFORMERS (Consistent)</div>
        <div id="leader-consistent" class="leaderboard"></div>
      </div>
    </div>

    <div style="margin-top:12px;font-size:12px;color:#bfead0">Last loaded: <span id="last-loaded">—</span></div>
  </div>

  <div id="day-corner" class="corner-day">—</div>

  <button class="refresh-btn" onclick="manualRefresh()">⟳</button>

  <script>
    let dataCache = null;
    async function fetchData(){
      try{
        const res = await fetch('/api/data');
        const json = await res.json();
        dataCache = json;
        render(json);
      } catch(e){
        console.error(e);
        alert('Failed to load data. Check console for details.');
      }
    }

    function cleanDisplayName(raw){
      if(!raw) return '';
      // remove leading /athletes/ or similar path segments, then trim
      return raw.toString().replace(/^\\/*athletes\\/*/i, '').trim();
    }

    function render(json){
      document.getElementById('total-athletes').innerText = json.summary.total_athletes;
      document.getElementById('days-running').innerText = json.summary.days_running;
      document.getElementById('consistent-count').innerText = json.summary.consistent_count;
      document.getElementById('top-distance').innerText = json.summary.top_distance_km.toFixed(2) + ' km';
      document.getElementById('last-loaded').innerText = new Date(json.loaded_at).toLocaleString();

      const n = json.summary.days_running;
      const suffix = (n%10===1 && n%100!==11)?'st':(n%10===2 && n%100!==12)?'nd':(n%10===3 && n%100!==13)?'rd':'th';
      document.getElementById('day-corner').innerText = `${n}${suffix} day of challenge`;

      renderLeaderboard('leader-total', json.leaderboards.total, true);
      renderLeaderboard('leader-walk', json.leaderboards.walk, false, 'walk_km');
      renderLeaderboard('leader-run', json.leaderboards.run, false, 'run_km');
      renderLeaderboard('leader-ride', json.leaderboards.ride, false, 'ride_km');
      renderConsistent('leader-consistent', json.consistent);
    }

    function renderLeaderboard(containerId, list, showId=false, kmField='km'){
      const el = document.getElementById(containerId);
      if(!list || list.length===0){ el.innerHTML = '<div class="small">No data</div>'; return }
      const rows = ['<table><thead><tr><th>#</th><th>Name</th>' + (showId?'<th>Athlete ID</th>':'') + '<th>KM</th></tr></thead><tbody>'];
      list.slice(0,50).forEach((r, i)=>{
        const posClass = i===0? 'pos1' : (i===1? 'pos2' : (i===2? 'pos3':''));
        const displayName = cleanDisplayName(r.name || r.athlete_id || '');
        const athleteId = r.athlete_id || '';
        const kmVal = (r[kmField]!==undefined)? r[kmField] : r.km;
        const consistentTag = (r.consistent)? '<span class="badge">ALL DAY</span>' : '';
        rows.push(`<tr class="${posClass}"><td>${i+1}</td><td>${displayName} ${consistentTag}</td>` + (showId?`<td>${athleteId}</td>`:'') + `<td>${(kmVal||0).toFixed(2)}</td></tr>`);
      });
      rows.push('</tbody></table>');
      el.innerHTML = rows.join('');
    }

    function renderConsistent(containerId, list){
      const el = document.getElementById(containerId);
      if(!list || list.length===0){ el.innerHTML = '<div class="small">No consistent performers yet</div>'; return }
      const rows = ['<table><thead><tr><th>#</th><th>Name</th><th>Athlete ID</th><th>Badge</th></tr></thead><tbody>'];
      list.forEach((r,i)=>{
        const displayName = cleanDisplayName(r.name || r.athlete_id || '');
        rows.push(`<tr class="${i===0?'pos1':''}"><td>${i+1}</td><td>${displayName}</td><td>${r.athlete_id}</td><td><span class="badge">ALL DAY PERFORMER</span></td></tr>`);
      });
      rows.push('</tbody></table>');
      el.innerHTML = rows.join('');
    }

    function applySearch(){
      const q = document.getElementById('search').value.toLowerCase().trim();
      if(!dataCache) return;
      if(!q){ render(dataCache); return }
      // filter leaderboards by cleaned display name or athlete id
      const filtered = JSON.parse(JSON.stringify(dataCache));
      Object.keys(filtered.leaderboards).forEach(key=>{
        filtered.leaderboards[key] = filtered.leaderboards[key].filter(r => {
          const displayName = (r.name || r.athlete_id || '').toString().toLowerCase().replace(/^\\/?athletes\\/?/,'').trim();
          const id = (r.athlete_id || '').toString().toLowerCase();
          return displayName.includes(q) || id.includes(q);
        });
      });
      filtered.consistent = filtered.consistent.filter(r => {
        const displayName = (r.name || r.athlete_id || '').toString().toLowerCase().replace(/^\\/?athletes\\/?/,'').trim();
        const id = (r.athlete_id || '').toString().toLowerCase();
        return displayName.includes(q) || id.includes(q);
      });
      render(filtered);
    }

    function manualRefresh(){ fetchData(); }

    // auto refresh (in milliseconds)
    fetchData();
    setInterval(fetchData, AUTO_REFRESH_INTERVAL);
  </script>
</body>
</html>
"""

# After declaring TEMPLATE, we will replace AUTO_REFRESH_INTERVAL with numeric ms value
TEMPLATE = TEMPLATE.replace("AUTO_REFRESH_INTERVAL",
                            str(AUTO_REFRESH_SECONDS * 1000))


# --- Utilities: load credentials, read sheet or fallback to local excel ---

def load_service_account_credentials():
    """Load service account credentials from env or credentials.json."""
    try:
        json_str = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_JSON')
        if json_str:
            info = json.loads(json_str)
            logger.info('Loaded credentials from env')
            creds = service_account.Credentials.from_service_account_info(
                info,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly',
                        'https://www.googleapis.com/auth/drive.readonly']
            )
            return creds
        if os.path.exists('credentials.json'):
            with open('credentials.json', 'r', encoding='utf-8') as f:
                info = json.load(f)
            logger.info('Loaded credentials.json')
            creds = service_account.Credentials.from_service_account_info(
                info,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly',
                        'https://www.googleapis.com/auth/drive.readonly']
            )
            return creds
    except Exception as e:
        logger.exception("Error loading credentials: %s", e)
    return None


def read_sheet_to_dataframe(creds):
    """Read Google Sheet if creds available; otherwise fallback to local Excel."""
    if creds:
        try:
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(SHEET_ID)
            ws = sh.get_worksheet(0)
            rows = ws.get_all_values()
            if not rows:
                raise ValueError("Sheet empty")
            headers = rows[0]
            data = rows[1:]
            df = pd.DataFrame(data, columns=headers)
            logger.info("Loaded sheet rows: %d", len(df))
            return df
        except Exception as e:
            logger.exception("Failed reading Google Sheet: %s", e)
    # local fallback
    try:
        if os.path.exists(LOCAL_XLSX_FALLBACK):
            logger.info("Using local fallback Excel: %s", LOCAL_XLSX_FALLBACK)
            df = pd.read_excel(LOCAL_XLSX_FALLBACK)
            return df
        else:
            raise FileNotFoundError("No credentials and no local fallback")
    except Exception as e:
        logger.exception("Failed to read local fallback: %s", e)
        raise


def clean_and_normalize_df(df):
    """
    Clean headers, prefer Name column for display name, parse dates and distances,
    create normalized columns used by the leaderboard logic.
    """
    df = df.copy()

    # normalize headers: strip quotes and whitespace and handle duplicates
    new_cols = []
    seen = {}
    for c in df.columns:
        if isinstance(c, str):
            h = c.strip().strip('"').strip("'")
        else:
            h = str(c)
        if h in seen:
            seen[h] += 1
            h2 = f"{h}__{seen[h]}"
        else:
            seen[h] = 0
            h2 = h
        new_cols.append(h2)
    df.columns = new_cols

    def find_col(cand_list):
        for cand in cand_list:
            for col in df.columns:
                if col.lower().strip() == cand.lower().strip() or cand.lower().strip() in col.lower():
                    return col
        return None

    # PREFER the human-friendly Name column over the Athlete path column
    col_athlete = find_col(['Name', 'Athlete', 'Athlete Name', 'athlete'])
    col_activity = find_col(['Activity', 'Activity Name'])
    col_type = find_col(['Type', 'Activity Type'])
    col_date = find_col(['Date', 'date'])
    col_distance = find_col(['Distance', 'distance', 'Dist', 'KM', 'Km'])
    col_unit = find_col(['Unit', 'unit'])
    col_athlete_id = find_col(['Athlete ID', 'AthleteID', 'athlete id', 'id'])

    # Canonical columns
    df['__athlete_name'] = df[col_athlete] if col_athlete in df.columns else df.iloc[:, 0]
    df['__athlete_id'] = df[col_athlete_id] if col_athlete_id in df.columns else df['__athlete_name']
    df['__activity'] = df[col_activity] if col_activity in df.columns else ''
    df['__type'] = df[col_type] if col_type in df.columns else ''
    df['__raw_date'] = df[col_date] if col_date in df.columns else None
    df['__distance_raw'] = df[col_distance] if col_distance in df.columns else None
    df['__unit'] = df[col_unit] if col_unit in df.columns else None

    # timezone-aware parser: convert timestamps (with offsets) to target tz then extract date
    TARGET_TZ = pytz.timezone('Asia/Kolkata')

    def parse_date_val(v):
        if pd.isna(v):
            return None

        # If it's already a datetime-like object
        if isinstance(v, (datetime, pd.Timestamp)):
            t = pd.to_datetime(v)
        else:
            # Let pandas parse the string (handles ISO with +05:30)
            t = pd.to_datetime(str(v), errors='coerce')

        if pd.isna(t):
            return None

        # If pandas produced a tz-aware timestamp:
        try:
            if getattr(t, 'tz', None) is not None and t.tz is not None:
                # convert to TARGET_TZ calendar date
                t_local = t.tz_convert(TARGET_TZ)
            else:
                # tz-naive: assume timestamps are already in TARGET_TZ local time
                # (alternative: localize as UTC then convert if your data is in UTC)
                t_local = TARGET_TZ.localize(t)
        except Exception:
            # last-resort: assume UTC then convert
            try:
                t = t.tz_localize('UTC')
                t_local = t.tz_convert(TARGET_TZ)
            except Exception:
                return None

        return t_local.date()

    df['__date'] = df['__raw_date'].apply(parse_date_val)

    # distance parsing and km conversion
    def parse_distance(row):
        v = row.get('__distance_raw')
        if pd.isna(v):
            return 0.0
        try:
            s = str(v).replace(',', '').strip()
            parts = s.split()
            num = float(parts[0])
        except Exception:
            try:
                num = float(pd.to_numeric(v, errors='coerce') or 0.0)
            except Exception:
                num = 0.0
        unit = row.get('__unit') or ''
        unit_s = str(unit).lower()
        if 'mile' in unit_s or 'mi' in unit_s:
            return num * 1.60934
        return float(num)

    df['__km'] = df.apply(parse_distance, axis=1)

    df['__type_norm'] = df['__type'].fillna('').astype(str).str.lower()
    df['__activity_norm'] = df['__activity'].fillna('').astype(str).str.lower()
    df['__athlete_id_str'] = df['__athlete_id'].astype(str).str.strip()
    df['__athlete_name_str'] = df['__athlete_name'].astype(str).str.strip()

    df = df[~(df['__athlete_id_str'].isna() & df['__athlete_name_str'].isna())]

    return df


def compute_leaderboards(df, today_date=None):
    # If no today_date provided, use the latest date present in the data (so we evaluate up to last logged day).
    if today_date is None:
        # derive today_date from the data's latest parsed date when available
        if '__date' in df.columns:
            try:
                valid_dates = pd.to_datetime(df['__date'], errors='coerce').dropna().dt.date
                if not valid_dates.empty:
                    today_date = valid_dates.max()
                else:
                    tz = pytz.timezone(TIMEZONE)
                    today_date = datetime.now(tz).date()
            except Exception:
                tz = pytz.timezone(TIMEZONE)
                today_date = datetime.now(tz).date()
        else:
            tz = pytz.timezone(TIMEZONE)
            today_date = datetime.now(tz).date()

    id_col = '__athlete_id_str'
    name_col = '__athlete_name_str'
    km_col = '__km'
    date_col = '__date'
    type_col = '__type_norm'
    activity_col = '__activity_norm'

    # aggregate per athlete: total, walk, run, ride
    grouped = df.groupby([id_col, name_col])
    records = []
    for (ath_id, ath_name), sub in grouped:
        total_km = float(sub[km_col].sum())
        walk_km = float(sub[(sub[type_col].str.contains(
            'walk', na=False) | sub[activity_col].str.contains('walk', na=False))][km_col].sum())
        run_km = float(sub[(sub[type_col].str.contains('run|jog', na=False) |
                       sub[activity_col].str.contains('run|jog', na=False))][km_col].sum())
        ride_km = float(sub[(sub[type_col].str.contains('ride|cycle|bike', na=False) |
                        sub[activity_col].str.contains('ride|cycle|bike', na=False))][km_col].sum())
        records.append({'athlete_id': str(ath_id), 'name': str(
            ath_name), 'total_km': total_km, 'walk_km': walk_km, 'run_km': run_km, 'ride_km': ride_km})

    agg_df = pd.DataFrame(records)
    if agg_df.empty:
        agg_df = pd.DataFrame(
            columns=['athlete_id', 'name', 'total_km', 'walk_km', 'run_km', 'ride_km'])

    # leaderboards sorted
    leader_total = agg_df.sort_values(
        'total_km', ascending=False).to_dict('records')
    leader_walk = agg_df.sort_values(
        'walk_km', ascending=False).to_dict('records')
    leader_run = agg_df.sort_values(
        'run_km', ascending=False).to_dict('records')
    leader_ride = agg_df.sort_values(
        'ride_km', ascending=False).to_dict('records')

    # consistent performers: must meet daily threshold for each day from START_DATE through today_date
    day_range = (today_date - START_DATE).days + 1
    required_days = [START_DATE + timedelta(days=i)
                     for i in range(max(0, day_range))]

    def qualifies_day(subdf, d):
        # select rows for that exact date (date column stores date objects)
        day_rows = subdf[subdf[date_col] == d]
        if day_rows.empty:
            return False

        # compute km and type for each activity that day
        # we'll sort by km descending and take top two activities
        day_rows_sorted = day_rows.sort_values(by=km_col, ascending=False)

        # take top two activities (or 1 if only one)
        top_two = day_rows_sorted.head(2)

        # sum their kms
        top_sum = float(top_two[km_col].sum())

        # determine if both top activities are ride-type
        is_ride_mask = (
            top_two[type_col].str.contains('ride|cycle|bike', na=False) |
            top_two[activity_col].str.contains('ride|cycle|bike', na=False)
        )
        both_ride = (is_ride_mask.sum() == len(top_two))

        # qualification thresholds:
        # - if both top activities are ride-type => require >=5.0 km
        # - otherwise (any walk/run present) => require >=2.0 km
        if both_ride:
            return top_sum >= 5.0
        else:
            return top_sum >= 2.0

    consistent_list = []
    for (ath_id, ath_name), sub in grouped:
        qualifies = True
        for d in required_days:
            if not qualifies_day(sub, d):
                qualifies = False
                break
        if qualifies and len(required_days) > 0:
            consistent_list.append(
                {'athlete_id': str(ath_id), 'name': str(ath_name)})

    # mark consistent flag on agg_df records
    agg_df['consistent'] = agg_df.apply(lambda r: any(
        (r['athlete_id'] == c['athlete_id']) for c in consistent_list), axis=1)

    total_athletes = df['__athlete_id_str'].nunique()
    days_running = max(0, (today_date - START_DATE).days + 1)
    consistent_count = len(consistent_list)
    top_distance_km = float(
        agg_df['total_km'].max() if not agg_df.empty else 0.0)

    return {
        'leaderboards': {
            'total': [{'athlete_id': r['athlete_id'], 'name': r['name'], 'km': r['total_km'], 'consistent': bool(r.get('consistent', False))} for r in leader_total],
            'walk': [{'athlete_id': r['athlete_id'], 'name': r['name'], 'walk_km': r['walk_km'], 'consistent': bool(r.get('consistent', False))} for r in leader_walk],
            'run': [{'athlete_id': r['athlete_id'], 'name': r['name'], 'run_km': r['run_km'], 'consistent': bool(r.get('consistent', False))} for r in leader_run],
            'ride': [{'athlete_id': r['athlete_id'], 'name': r['name'], 'ride_km': r['ride_km'], 'consistent': bool(r.get('consistent', False))} for r in leader_ride]
        },
        'consistent': consistent_list,
        'summary': {
            'total_athletes': int(total_athletes),
            'days_running': int(days_running),
            'consistent_count': int(consistent_count),
            'top_distance_km': float(top_distance_km)
        }
    }


@app.route('/')
def index():
    return render_template_string(TEMPLATE)


@app.route('/api/data')
def api_data():
    try:
        creds = load_service_account_credentials()
        df_raw = read_sheet_to_dataframe(creds)
        df = clean_and_normalize_df(df_raw)
        results = compute_leaderboards(df)
        tz = pytz.timezone(TIMEZONE)
        payload = {
            'leaderboards': results['leaderboards'],
            'consistent': results['consistent'],
            'summary': results['summary'],
            'loaded_at': datetime.now(tz).isoformat()
        }
        return jsonify(payload)
    except Exception as e:
        logger.exception("Failed to build API data: %s", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # for local debugging
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
