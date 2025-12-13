"""
GEF Winter Challenge Dashboard - Simplified
- Searchable individual scores
- Team performance bar chart
"""

import os
import pytz
import json
import logging
from datetime import datetime
import pandas as pd
from flask import Flask, render_template_string, jsonify, request
from google.oauth2 import service_account
import gspread

# Config
SHEET_ID = os.environ.get(
    'SHEET_ID', '1PF9liQPShcqMPNBScmV1_V3kUFaZcmlIHy8TLM4AmJc')
TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Kolkata')
AUTO_REFRESH_SECONDS = int(os.environ.get('AUTO_REFRESH_SECONDS', '300'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('gef_dashboard')

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>GEF Winter Challenge</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    html,body{height:100%;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto}
    body{background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;padding:20px}
    .container{max-width:1200px;margin:0 auto}
    .header{text-align:center;margin-bottom:30px}
    h1{font-size:28px;font-weight:800;background:linear-gradient(90deg,#10b981,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}
    .card{background:rgba(30,41,59,0.6);backdrop-filter:blur(10px);border:1px solid rgba(148,163,184,0.1);border-radius:12px;padding:24px;margin:20px 0;box-shadow:0 10px 40px rgba(0,0,0,0.3)}
    .section-title{font-size:20px;font-weight:700;color:#10b981;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid rgba(16,185,129,0.3);display:flex;align-items:center;gap:10px}
    .chart-container{background:rgba(15,23,42,0.6);padding:20px;border-radius:10px;margin-top:16px;min-height:400px}
    canvas{max-height:380px}
    
    /* Search Section */
    .search-container{max-width:600px;margin:0 auto 30px;position:relative}
    .search-wrapper{position:relative}
    .search-box{width:100%;padding:16px 50px 16px 20px;font-size:16px;background:rgba(15,23,42,0.8);border:2px solid rgba(16,185,129,0.3);border-radius:10px;color:#e2e8f0;outline:none;transition:all 0.3s}
    .search-box:focus{border-color:#10b981;box-shadow:0 0 20px rgba(16,185,129,0.3)}
    .search-box::placeholder{color:#64748b}
    .clear-btn{position:absolute;right:12px;top:50%;transform:translateY(-50%);background:rgba(239,68,68,0.8);color:white;border:none;padding:8px 12px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;transition:all 0.2s;display:none}
    .clear-btn:hover{background:rgba(239,68,68,1);transform:translateY(-50%) scale(1.05)}
    .clear-btn.visible{display:block}
    
    .result-card{background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(59,130,246,0.15));border:2px solid rgba(16,185,129,0.3);border-radius:10px;padding:24px;margin-top:20px;text-align:center}
    .result-name{font-size:24px;font-weight:700;color:#10b981;margin-bottom:12px}
    .team-tag{display:inline-block;background:linear-gradient(135deg,#3b82f6,#2563eb);color:white;padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;margin-bottom:16px;letter-spacing:0.5px}
    .result-points{font-size:48px;font-weight:800;color:#3b82f6;margin-bottom:8px}
    .result-label{font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1px}
    
    .no-result{color:#94a3b8;text-align:center;padding:30px;font-size:14px}
    .suggestions{margin-top:16px;max-height:200px;overflow-y:auto;background:rgba(15,23,42,0.95);border:1px solid rgba(148,163,184,0.2);border-radius:8px;display:none}
    .suggestion-item{padding:12px 16px;cursor:pointer;border-bottom:1px solid rgba(148,163,184,0.1);transition:background 0.2s}
    .suggestion-item:hover{background:rgba(16,185,129,0.2)}
    .suggestion-item:last-child{border-bottom:none}
    
    .refresh-btn{position:fixed;right:20px;bottom:20px;background:linear-gradient(135deg,#10b981,#059669);color:white;border:none;padding:16px;border-radius:50%;box-shadow:0 8px 24px rgba(16,185,129,0.4);cursor:pointer;font-size:20px;transition:transform 0.2s;z-index:1000}
    .refresh-btn:hover{transform:scale(1.1)}
    
    @media(max-width:768px){
      body{padding:12px}
      h1{font-size:22px}
      .card{padding:16px}
      .section-title{font-size:16px}
      .result-points{font-size:36px}
      .chart-container{min-height:300px;padding:12px}
      canvas{max-height:280px}
    }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🏃 GEF Winter Challenge</h1>
      <p style="color:#94a3b8;font-size:14px">Team Performance & Individual Scores</p>
    </div>

    <!-- Team Performance Chart -->
    <div class="card">
      <div class="section-title">
        <span>🏆</span>
        <span>Team Points - Bar Chart</span>
      </div>
      <div class="chart-container">
        <canvas id="teamChart"></canvas>
      </div>
    </div>

    <!-- Search Section -->
    <div class="card">
      <div class="section-title">
        <span>🔍</span>
        <span>Search Your Score</span>
      </div>
      <div class="search-container">
        <div class="search-wrapper">
          <input 
            type="text" 
            id="searchBox" 
            class="search-box" 
            placeholder="Type your name to search..."
            autocomplete="off"
          >
          <button id="clearBtn" class="clear-btn">✕ Clear</button>
        </div>
        <div id="suggestions" class="suggestions"></div>
        <div id="searchResult"></div>
      </div>
    </div>

    <div style="margin-top:30px;text-align:center;color:#64748b;font-size:12px">
      Last updated: <span id="lastUpdated">—</span>
    </div>
  </div>

  <button class="refresh-btn" onclick="loadData()">⟳</button>

  <script>
    let teamChartInstance = null;
    let allAthletes = [];

    async function loadData(){
      try{
        const res = await fetch('/api/data');
        const data = await res.json();
        
        allAthletes = data.athletes;
        renderTeamChart(data.teams);
        
        document.getElementById('lastUpdated').textContent = new Date(data.loaded_at).toLocaleString();
      }catch(e){
        console.error('Failed to load data:', e);
      }
    }

    function renderTeamChart(teams){
      const ctx = document.getElementById('teamChart').getContext('2d');
      
      const sorted = [...teams].sort((a,b) => b.points - a.points);
      const labels = sorted.map(t => t.team);
      const points = sorted.map(t => t.points);

      if(teamChartInstance) teamChartInstance.destroy();

      teamChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Points',
            data: points,
            backgroundColor: 'rgba(16, 185, 129, 0.8)',
            borderColor: 'rgba(16, 185, 129, 1)',
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {display: false},
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.parsed.y.toFixed(1)} points`
              }
            },
            datalabels: {
              display: true,
              anchor: 'center',
              align: 'center',
              rotation: -90,
              color: 'white',
              font: {
                weight: 'bold',
                size: window.innerWidth < 768 ? 11 : 14
              },
              formatter: (value) => value.toFixed(1)
            }
          },
          scales: {
            x: {
              ticks: {
                color: '#94a3b8',
                font: {size: window.innerWidth < 768 ? 11 : 14, weight: 'bold'}
              },
              grid: {display: false}
            },
            y: {
              title: {display: true, text: 'Points', color: '#94a3b8', font: {size: 13}},
              ticks: {color: '#94a3b8', font: {size: 12}},
              grid: {color: 'rgba(148,163,184,0.1)'}
            }
          }
        }
      });
    }

    // Search functionality
    const searchBox = document.getElementById('searchBox');
    const clearBtn = document.getElementById('clearBtn');
    const suggestionsDiv = document.getElementById('suggestions');
    const resultDiv = document.getElementById('searchResult');

    searchBox.addEventListener('input', (e) => {
      const query = e.target.value.trim().toLowerCase();
      
      // Show/hide clear button
      if(query.length > 0){
        clearBtn.classList.add('visible');
      }else{
        clearBtn.classList.remove('visible');
      }
      
      if(query.length === 0){
        suggestionsDiv.style.display = 'none';
        suggestionsDiv.innerHTML = '';
        resultDiv.innerHTML = '';
        return;
      }

      const matches = allAthletes.filter(a => 
        a.name.toLowerCase().includes(query)
      ).slice(0, 10);

      if(matches.length > 0){
        suggestionsDiv.style.display = 'block';
        suggestionsDiv.innerHTML = matches.map(a => 
          `<div class="suggestion-item" onclick="selectAthlete('${a.athlete_id}')">
            ${a.name} - ${a.team}
          </div>`
        ).join('');
      }else{
        suggestionsDiv.style.display = 'none';
      }

      if(matches.length === 1 || (matches.length > 0 && matches[0].name.toLowerCase() === query)){
        selectAthlete(matches[0].athlete_id);
      }
    });

    // Clear button functionality
    clearBtn.addEventListener('click', () => {
      searchBox.value = '';
      clearBtn.classList.remove('visible');
      suggestionsDiv.style.display = 'none';
      suggestionsDiv.innerHTML = '';
      resultDiv.innerHTML = '';
      searchBox.focus();
    });

    function selectAthlete(athleteId){
      const athlete = allAthletes.find(a => a.athlete_id === athleteId);
      if(!athlete){
        resultDiv.innerHTML = '<div class="no-result">Athlete not found</div>';
        return;
      }

      searchBox.value = athlete.name;
      suggestionsDiv.style.display = 'none';
      clearBtn.classList.add('visible');
      
      resultDiv.innerHTML = `
        <div class="result-card">
          <div class="result-name">${athlete.name}</div>
          <div class="team-tag">${athlete.team}</div>
          <div class="result-points">${athlete.points.toFixed(1)}</div>
          <div class="result-label">Total Points</div>
        </div>
      `;
    }

    // Hide suggestions when clicking outside
    document.addEventListener('click', (e) => {
      if(!searchBox.contains(e.target) && !suggestionsDiv.contains(e.target)){
        suggestionsDiv.style.display = 'none';
      }
    });

    loadData();
    setInterval(loadData, AUTO_REFRESH_INTERVAL);
  </script>
</body>
</html>
""".replace("AUTO_REFRESH_INTERVAL", str(AUTO_REFRESH_SECONDS * 1000))


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


def read_google_sheet(creds, sheet_name):
    """Read a specific worksheet from Google Sheets."""
    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        rows = ws.get_all_values()
        if not rows:
            return pd.DataFrame()
        headers = rows[0]
        data = rows[1:]
        df = pd.DataFrame(data, columns=headers)
        logger.info(f"Loaded {sheet_name}: {len(df)} rows")
        return df
    except Exception as e:
        logger.exception(f"Failed reading sheet {sheet_name}: %s", e)
        return pd.DataFrame()


def compute_data(daily_df, team_df, summary_df):
    """Compute individual athlete scores and team totals."""

    # Clean column names
    daily_df.columns = [str(c).strip() for c in daily_df.columns]
    team_df.columns = [str(c).strip() for c in team_df.columns]
    summary_df.columns = [str(c).strip() for c in summary_df.columns]

    # Create athlete_id to team mapping
    team_map = {}
    for _, row in team_df.iterrows():
        strava_id = str(row.get('STRAVA_ID', '')).strip()
        team_id = str(row.get('TEAM_ID', '')).strip()
        if not team_id:
            team_id = str(row.get('TEAM', '')).strip()
        if strava_id and team_id:
            team_map[strava_id] = team_id

    # Parse daily data
    daily_df['athlete_id'] = daily_df['Athlete'].astype(str).str.strip()
    daily_df['athlete_name'] = daily_df['Name'].astype(str).str.strip()
    daily_df['points'] = pd.to_numeric(daily_df.get(
        'CalcTotal', 0), errors='coerce').fillna(0)

    # Map teams
    daily_df['team'] = daily_df['athlete_id'].map(team_map).fillna('Unknown')

    # Aggregate by athlete - sum all their points
    athlete_stats = daily_df.groupby(['athlete_name', 'athlete_id', 'team'])[
        'points'].sum().reset_index()
    athlete_stats.columns = ['name', 'athlete_id', 'team', 'points']
    athlete_list = athlete_stats.to_dict('records')

    # Parse team summary data
    teams_data = []
    for _, row in summary_df.iterrows():
        team = str(row.get('TEAM', '')).strip()
        points = float(pd.to_numeric(
            row.get('POINT', 0), errors='coerce') or 0)
        if team:
            teams_data.append({'team': team, 'points': points})

    return {
        'athletes': athlete_list,
        'teams': teams_data
    }


@app.route('/')
def index():
    return render_template_string(TEMPLATE)


@app.route('/api/data')
def api_data():
    try:
        creds = load_service_account_credentials()
        if not creds:
            return jsonify({'error': 'No credentials available'}), 500

        # Read sheets
        daily_df = read_google_sheet(creds, 'DAILY-UPDATE')
        team_df = read_google_sheet(creds, 'TEAM DATA')
        summary_df = read_google_sheet(creds, 'SUMMARY')

        if daily_df.empty or team_df.empty or summary_df.empty:
            return jsonify({'error': 'One or more sheets are empty'}), 500

        results = compute_data(daily_df, team_df, summary_df)

        tz = pytz.timezone(TIMEZONE)
        payload = {
            'athletes': results['athletes'],
            'teams': results['teams'],
            'loaded_at': datetime.now(tz).isoformat()
        }

        return jsonify(payload)
    except Exception as e:
        logger.exception("Failed to build API data: %s", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
