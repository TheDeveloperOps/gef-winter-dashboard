"""
GEF Winter Challenge Dashboard - Complete with Gender Leaderboards
- Mobile-first design with larger fonts for aged users
- Team bar chart
- 4 Gender-based leaderboards (Men/Women Run-Walk/Ride)
- Individual activity search
"""

import os
import pytz
import json
import logging
from datetime import datetime, date
import pandas as pd
from flask import Flask, render_template_string, jsonify
from google.oauth2 import service_account
import gspread

SHEET_ID = os.environ.get(
    'SHEET_ID', '1PF9liQPShcqMPNBScmV1_V3kUFaZcmlIHy8TLM4AmJc')
TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Kolkata')
AUTO_REFRESH_SECONDS = int(os.environ.get('AUTO_REFRESH_SECONDS', '300'))
START_DATE = date(2025, 11, 16)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('gef_dashboard')

app = Flask(__name__)

MAIN_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>GEF Winter Challenge</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    html,body{height:100%;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto;font-size:16px}
    body{background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;padding:12px 16px}
    .container{max-width:1400px;margin:0 auto}
    .header{text-align:center;margin-bottom:24px;padding:16px 0}
    h1{font-size:28px;font-weight:800;background:linear-gradient(90deg,#10b981,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px;line-height:1.2}
    .subtitle{color:#94a3b8;font-size:15px;font-weight:600}
    
    .card{background:rgba(30,41,59,0.7);backdrop-filter:blur(10px);border:1px solid rgba(148,163,184,0.15);border-radius:12px;padding:20px;margin:20px 0;box-shadow:0 10px 40px rgba(0,0,0,0.3)}
    .section-title{font-size:20px;font-weight:800;color:#10b981;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid rgba(16,185,129,0.4);display:flex;align-items:center;gap:10px;line-height:1.3}
    
    .chart-container{background:rgba(15,23,42,0.7);padding:16px;border-radius:10px;margin-top:12px;min-height:500px;cursor:pointer}
    canvas{max-height:480px;width:100%!important;height:480px!important}
    
    /* Leaderboards Grid */
    .leaderboards-grid{display:grid;grid-template-columns:1fr;gap:16px;margin:20px 0}
    .leaderboard-card{background:rgba(30,41,59,0.7);backdrop-filter:blur(10px);border:1px solid rgba(148,163,184,0.15);border-radius:12px;padding:18px}
    .leaderboard-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
    .leaderboard-title{font-size:16px;font-weight:800;color:#10b981}
    .search-mini{width:140px;padding:8px 12px;font-size:14px;background:rgba(15,23,42,0.8);border:1px solid rgba(16,185,129,0.3);border-radius:6px;color:#e2e8f0;outline:none}
    .search-mini:focus{border-color:#10b981}
    .search-mini::placeholder{color:#64748b;font-size:13px}
    
    .leaderboard-list{max-height:280px;overflow-y:auto;margin-top:10px}
    .leaderboard-list::-webkit-scrollbar{width:6px}
    .leaderboard-list::-webkit-scrollbar-track{background:rgba(30,41,59,0.4);border-radius:10px}
    .leaderboard-list::-webkit-scrollbar-thumb{background:rgba(16,185,129,0.6);border-radius:10px}
    
    .athlete-item{display:flex;justify-content:space-between;align-items:center;padding:12px;margin:4px 0;background:rgba(15,23,42,0.5);border-radius:8px;transition:all 0.2s}
    .athlete-item:hover{background:rgba(16,185,129,0.15);transform:translateX(4px)}
    .athlete-rank{font-weight:800;color:#10b981;min-width:35px;font-size:16px}
    .athlete-name{flex:1;font-weight:600;font-size:15px;color:#e2e8f0}
    .athlete-points{font-weight:800;color:#3b82f6;font-size:16px}
    
    .rank-1{background:linear-gradient(90deg,rgba(251,191,36,0.3),rgba(15,23,42,0.5))}
    .rank-2{background:linear-gradient(90deg,rgba(203,213,225,0.3),rgba(15,23,42,0.5))}
    .rank-3{background:linear-gradient(90deg,rgba(205,127,50,0.3),rgba(15,23,42,0.5))}
    
    /* Search Section */
    .search-container{max-width:700px;margin:0 auto;position:relative}
    .search-wrapper{position:relative}
    .search-box{width:100%;padding:18px 60px 18px 20px;font-size:17px;font-weight:600;background:rgba(15,23,42,0.8);border:2px solid rgba(16,185,129,0.3);border-radius:10px;color:#e2e8f0;outline:none;transition:all 0.3s}
    .search-box:focus{border-color:#10b981;box-shadow:0 0 20px rgba(16,185,129,0.3)}
    .search-box::placeholder{color:#64748b;font-size:16px}
    .clear-btn{position:absolute;right:12px;top:50%;transform:translateY(-50%);background:rgba(239,68,68,0.8);color:white;border:none;padding:10px 14px;border-radius:8px;cursor:pointer;font-size:15px;font-weight:700;transition:all 0.2s;display:none}
    .clear-btn:hover{background:rgba(239,68,68,1)}
    .clear-btn.visible{display:block}
    
    .result-card{background:linear-gradient(135deg,rgba(16,185,129,0.2),rgba(59,130,246,0.2));border:2px solid rgba(16,185,129,0.4);border-radius:12px;padding:24px;margin-top:20px;text-align:center}
    .result-name{font-size:26px;font-weight:800;color:#10b981;margin-bottom:12px}
    .team-tag{display:inline-block;background:linear-gradient(135deg,#3b82f6,#2563eb);color:white;padding:8px 20px;border-radius:24px;font-size:15px;font-weight:800;margin-bottom:16px;letter-spacing:0.5px}
    .result-points{font-size:52px;font-weight:900;color:#3b82f6;margin-bottom:8px;line-height:1}
    .result-label{font-size:14px;color:#64748b;text-transform:uppercase;letter-spacing:1px;font-weight:700}
    
    .suggestions{margin-top:16px;max-height:240px;overflow-y:auto;background:rgba(15,23,42,0.95);border:1px solid rgba(148,163,184,0.2);border-radius:8px;display:none}
    .suggestion-item{padding:14px 18px;cursor:pointer;border-bottom:1px solid rgba(148,163,184,0.1);transition:background 0.2s;font-size:15px;font-weight:600}
    .suggestion-item:hover{background:rgba(16,185,129,0.2)}
    .suggestion-item:last-child{border-bottom:none}
    
    .activity-table{width:100%;margin-top:20px;overflow-x:auto;-webkit-overflow-scrolling:touch}
    .activity-table table{width:100%;border-collapse:collapse;font-size:14px;background:rgba(15,23,42,0.7);border-radius:8px;overflow:hidden}
    .activity-table th{background:rgba(16,185,129,0.3);padding:14px 10px;text-align:center;font-weight:800;color:#10b981;border-bottom:2px solid rgba(16,185,129,0.4);position:sticky;top:0;z-index:10;font-size:14px}
    .activity-table td{padding:12px 10px;text-align:center;border-bottom:1px solid rgba(148,163,184,0.1);color:#e2e8f0;font-size:14px;font-weight:600}
    .activity-table tr:hover{background:rgba(16,185,129,0.1)}
    .activity-table th:first-child,.activity-table td:first-child{text-align:left;padding-left:16px;position:sticky;left:0;background:rgba(15,23,42,0.95);z-index:5;font-weight:800}
    .activity-table th:first-child{z-index:15;background:rgba(16,185,129,0.3)}
    
    .refresh-btn{position:fixed;right:16px;bottom:16px;background:linear-gradient(135deg,#10b981,#059669);color:white;border:none;padding:18px;border-radius:50%;box-shadow:0 8px 24px rgba(16,185,129,0.4);cursor:pointer;font-size:22px;transition:transform 0.2s;z-index:1000;width:60px;height:60px;display:flex;align-items:center;justify-content:center}
    .refresh-btn:hover{transform:scale(1.1)}
    
    .no-result{color:#94a3b8;text-align:center;padding:30px;font-size:15px;font-weight:600}
    
    @media(min-width:768px){
      body{padding:24px;font-size:15px}
      h1{font-size:32px}
      .subtitle{font-size:16px}
      .leaderboards-grid{grid-template-columns:repeat(2,1fr);gap:20px}
      .chart-container{min-height:420px;padding:20px}
      canvas{max-height:400px!important;height:400px!important}
      .card{padding:28px}
    }
    
    @media(min-width:1200px){
      .leaderboards-grid{grid-template-columns:repeat(4,1fr)}
    }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🏃 GEF Winter Challenge</h1>
      <p class="subtitle">Team Performance & Leaderboards</p>
      <p style="color:#64748b;font-size:13px;font-weight:600;margin-top:8px">
        Sheet Updated: <span id="sheetUpdated" style="color:#10b981;font-weight:700">—</span>
      </p>
    </div>

    <!-- Team Chart -->
    <div class="card">
      <div class="section-title">
        <span>🏆</span>
        <span>Team Points - Click Bar for Details</span>
      </div>
      <div style="background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);border-radius:8px;padding:12px;margin-bottom:12px;text-align:center">
        <span style="font-size:14px;font-weight:700;color:#10b981">💡 Tip:</span>
        <span style="font-size:14px;font-weight:600;color:#e2e8f0"> Tap any bar to see team members & details</span>
      </div>
      <div class="chart-container">
        <canvas id="teamChart"></canvas>
      </div>
    </div>

    <!-- 4 Leaderboards -->
    <div class="leaderboards-grid">
      <div class="leaderboard-card">
        <div class="leaderboard-header">
          <div class="leaderboard-title">👨 Men Run/Walk</div>
          <input type="text" class="search-mini" placeholder="Search..." id="searchMenRun">
        </div>
        <div class="leaderboard-list" id="menRunList"></div>
      </div>

      <div class="leaderboard-card">
        <div class="leaderboard-header">
          <div class="leaderboard-title">👩 Women Run/Walk</div>
          <input type="text" class="search-mini" placeholder="Search..." id="searchWomenRun">
        </div>
        <div class="leaderboard-list" id="womenRunList"></div>
      </div>

      <div class="leaderboard-card">
        <div class="leaderboard-header">
          <div class="leaderboard-title">👨 Men Ride</div>
          <input type="text" class="search-mini" placeholder="Search..." id="searchMenRide">
        </div>
        <div class="leaderboard-list" id="menRideList"></div>
      </div>

      <div class="leaderboard-card">
        <div class="leaderboard-header">
          <div class="leaderboard-title">👩 Women Ride</div>
          <input type="text" class="search-mini" placeholder="Search..." id="searchWomenRide">
        </div>
        <div class="leaderboard-list" id="womenRideList"></div>
      </div>
    </div>

    <!-- Individual Search -->
    <div class="card">
      <div class="section-title">
        <span>🔍</span>
        <span>Search Your Activity Details</span>
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
          <button id="clearBtn" class="clear-btn">✕</button>
        </div>
        <div id="suggestions" class="suggestions"></div>
        <div id="searchResult"></div>
      </div>
    </div>

    <div style="margin-top:30px;text-align:center;color:#64748b;font-size:13px;font-weight:600">
      Last updated: <span id="lastUpdated">—</span>
    </div>
  </div>

  <button class="refresh-btn" onclick="loadData()">⟳</button>

  <script>
    let teamChartInstance = null;
    let allAthletes = [];
    let leaderboards = {};

    async function loadData(){
      try{
        const res = await fetch('/api/data');
        const data = await res.json();
        
        allAthletes = data.athletes;
        leaderboards = data.leaderboards;
        
        renderTeamChart(data.teams);
        renderLeaderboard('menRunList', leaderboards.men_run, 'searchMenRun');
        renderLeaderboard('womenRunList', leaderboards.women_run, 'searchWomenRun');
        renderLeaderboard('menRideList', leaderboards.men_ride, 'searchMenRide');
        renderLeaderboard('womenRideList', leaderboards.women_ride, 'searchWomenRide');
        
        document.getElementById('sheetUpdated').textContent = data.sheet_updated || '—';
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
            borderWidth: 2,
            teamNames: labels
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          onClick: (e, activeEls) => {
            if(activeEls.length > 0){
              const index = activeEls[0].index;
              window.location.href = '/team/' + sorted[index].team;
            }
          },
          plugins: {
            legend: {display: false},
            tooltip: {
              callbacks: {
                label: (ctx) => ctx.parsed.y.toFixed(1) + ' points'
              }
            },
            datalabels: {
              display: (context) => true,
              font: (context) => {
                return {
                  weight: 'bold',
                  size: window.innerWidth < 768 ? 11 : 12
                };
              },
              color: 'white',
              formatter: (value, context) => {
                const teamName = context.chart.data.datasets[0].teamNames[context.dataIndex];
                const points = value.toFixed(1);
                return [teamName, points];
              },
              rotation: -90,
              anchor: 'center',
              align: 'center',
              offset: 0,
              textAlign: 'center',
              padding: 4
            }
          },
          scales: {
            x: {
              ticks: {color: '#94a3b8', font: {size: window.innerWidth < 768 ? 14 : 13, weight: 'bold'}},
              grid: {display: false}
            },
            y: {
              title: {display: true, text: 'Points', color: '#94a3b8', font: {size: window.innerWidth < 768 ? 15 : 13, weight: 'bold'}},
              ticks: {color: '#94a3b8', font: {size: window.innerWidth < 768 ? 14 : 12}},
              grid: {color: 'rgba(148,163,184,0.1)'}
            }
          }
        }
      });
    }

    function renderLeaderboard(listId, athletes, searchId){
      const container = document.getElementById(listId);
      const searchBox = document.getElementById(searchId);
      
      // Add original rank to each athlete
      let allAthletes = athletes.map((a, i) => ({...a, originalRank: i + 1}));
      
      function render(filtered){
        if(!filtered || filtered.length === 0){
          container.innerHTML = '<div class="no-result">No athletes found</div>';
          return;
        }
        
        let html = '';
        filtered.forEach((a, i) => {
          const rankClass = a.originalRank === 1 ? 'rank-1' : a.originalRank === 2 ? 'rank-2' : a.originalRank === 3 ? 'rank-3' : '';
          html += '<div class="athlete-item ' + rankClass + '">';
          html += '<span class="athlete-rank">' + a.originalRank + '</span>';
          html += '<span class="athlete-name">' + a.name + '</span>';
          html += '<span class="athlete-points">' + a.points.toFixed(1) + '</span>';
          html += '</div>';
        });
        container.innerHTML = html;
      }
      
      render(allAthletes);
      
      searchBox.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        if(query === ''){
          render(allAthletes);
        }else{
          const filtered = allAthletes.filter(a => a.name.toLowerCase().includes(query));
          render(filtered);
        }
      });
    }

    const searchBox = document.getElementById('searchBox');
    const clearBtn = document.getElementById('clearBtn');
    const suggestionsDiv = document.getElementById('suggestions');
    const resultDiv = document.getElementById('searchResult');

    searchBox.addEventListener('input', (e) => {
      const query = e.target.value.trim().toLowerCase();
      
      clearBtn.classList.toggle('visible', query.length > 0);
      
      if(query.length === 0){
        suggestionsDiv.style.display = 'none';
        suggestionsDiv.innerHTML = '';
        resultDiv.innerHTML = '';
        return;
      }

      const matches = allAthletes.filter(a => a.name.toLowerCase().includes(query)).slice(0, 10);

      if(matches.length > 0){
        suggestionsDiv.style.display = 'block';
        suggestionsDiv.innerHTML = matches.map(a => 
          '<div class="suggestion-item" onclick="selectAthlete(\\'' + a.athlete_id + '\\')">'+
            a.name + ' - ' + a.team +
          '</div>'
        ).join('');
      }else{
        suggestionsDiv.style.display = 'none';
      }
    });

    clearBtn.addEventListener('click', () => {
      searchBox.value = '';
      clearBtn.classList.remove('visible');
      suggestionsDiv.style.display = 'none';
      suggestionsDiv.innerHTML = '';
      resultDiv.innerHTML = '';
      searchBox.focus();
    });

    async function selectAthlete(athleteId){
      const athlete = allAthletes.find(a => a.athlete_id === athleteId);
      if(!athlete){
        resultDiv.innerHTML = '<div class="no-result">Athlete not found</div>';
        return;
      }

      searchBox.value = athlete.name;
      suggestionsDiv.style.display = 'none';
      clearBtn.classList.add('visible');
      
      resultDiv.innerHTML = '<div style="text-align:center;padding:20px;color:#94a3b8;font-weight:600">Loading...</div>';
      
      try{
        const res = await fetch('/api/athlete/' + athleteId);
        const data = await res.json();
        
        let html = '<div class="result-card">';
        html += '<div class="result-name">' + athlete.name + '</div>';
        html += '<div class="team-tag">' + athlete.team + '</div>';
        html += '<div class="result-points">' + athlete.points.toFixed(1) + '</div>';
        html += '<div class="result-label">Total Points</div>';
        html += '</div>';
        
        if(data.daily_activities && data.daily_activities.length > 0){
          html += '<div class="activity-table">';
          html += '<table><thead><tr><th>Type</th>';
          data.dates.forEach(d => {
            html += '<th>' + d + '</th>';
          });
          html += '<th>Total</th><th>Active</th></tr></thead><tbody>';
          
          data.daily_activities.forEach(row => {
            html += '<tr><td>' + row.type + '</td>';
            data.dates.forEach(d => {
              const val = row.values[d] || '-';
              html += '<td>' + (val === '-' ? val : val.toFixed(1)) + '</td>';
            });
            html += '<td><strong>' + row.total.toFixed(1) + '</strong></td>';
            html += '<td>' + row.active_days + '</td>';
            html += '</tr>';
          });
          
          html += '</tbody></table></div>';
        }
        
        resultDiv.innerHTML = html;
      }catch(e){
        console.error('Failed to load athlete details:', e);
        resultDiv.innerHTML = '<div class="no-result">Failed to load details</div>';
      }
    }

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

TEAM_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
  <title>{{ team_id }} - Team Details</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    html,body{height:100%;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto}
    body{background:linear-gradient(135deg,#0f172a,#1e293b);color:#e2e8f0;padding:20px}
    .container{max-width:1200px;margin:0 auto}
    .header{text-align:center;margin-bottom:30px}
    h1{font-size:26px;font-weight:800;background:linear-gradient(90deg,#10b981,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:10px}
    .back-btn{display:inline-block;background:rgba(59,130,246,0.8);color:white;padding:12px 24px;border-radius:8px;text-decoration:none;margin-bottom:20px;transition:all 0.2s;font-weight:700;font-size:15px}
    .back-btn:hover{background:rgba(59,130,246,1);transform:translateY(-2px)}
    .card{background:rgba(30,41,59,0.6);backdrop-filter:blur(10px);border:1px solid rgba(148,163,184,0.1);border-radius:12px;padding:24px;margin:20px 0;box-shadow:0 10px 40px rgba(0,0,0,0.3)}
    .section-title{font-size:20px;font-weight:800;color:#10b981;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid rgba(16,185,129,0.3)}
    .team-table{width:100%;overflow-x:auto}
    .team-table table{width:100%;border-collapse:collapse;font-size:15px;background:rgba(15,23,42,0.6);border-radius:8px;overflow:hidden}
    .team-table th{background:rgba(16,185,129,0.2);padding:14px 12px;text-align:left;font-weight:800;color:#10b981;border-bottom:2px solid rgba(16,185,129,0.3)}
    .team-table td{padding:14px 12px;border-bottom:1px solid rgba(148,163,184,0.1);color:#e2e8f0;font-weight:600}
    .team-table tr:hover{background:rgba(16,185,129,0.1)}
    .team-table th:nth-child(2),.team-table td:nth-child(2),
    .team-table th:nth-child(3),.team-table td:nth-child(3),
    .team-table th:nth-child(4),.team-table td:nth-child(4){text-align:right}
  </style>
</head>
<body>
  <div class="container">
    <a href="/" class="back-btn">← Back to Dashboard</a>
    
    <div class="header">
      <h1>{{ team_id }} - Team Details</h1>
      <p style="color:#94a3b8;font-size:16px;font-weight:600">Total: <strong style="color:#10b981;font-size:18px">{{ total_points }}</strong> points</p>
    </div>

    <div class="card">
      <div class="section-title">Team Members ({{ member_count }})</div>
      <div class="team-table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Run/Walk</th>
              <th>Ride</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {% for member in members %}
            <tr>
              <td>{{ member.name }}</td>
              <td>{{ member.run_walk_points }}</td>
              <td>{{ member.ride_points }}</td>
              <td><strong>{{ member.total_points }}</strong></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    
    <div style="margin-top:30px;text-align:center;color:#64748b;font-size:13px;font-weight:600">
      Last updated: {{ updated_at }}
    </div>
  </div>
</body>
</html>
"""


def load_service_account_credentials():
    try:
        json_str = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_JSON')
        if json_str:
            info = json.loads(json_str)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly',
                              'https://www.googleapis.com/auth/drive.readonly'])
            return creds
        if os.path.exists('credentials.json'):
            with open('credentials.json', 'r', encoding='utf-8') as f:
                info = json.load(f)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly',
                              'https://www.googleapis.com/auth/drive.readonly'])
            return creds
    except Exception as e:
        logger.exception("Error loading credentials: %s", e)
    return None


def read_google_sheet(creds, sheet_name):
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


def compute_main_data(daily_df, summary_df, team_df):
    daily_df.columns = [str(c).strip() for c in daily_df.columns]
    summary_df.columns = [str(c).strip() for c in summary_df.columns]
    team_df.columns = [str(c).strip() for c in team_df.columns]

    # Find most recent date in the sheet
    sheet_updated = "Unknown"
    try:
        daily_df['date_extract_parsed'] = pd.to_datetime(
            daily_df['DATE_EXTRACT'], errors='coerce')
        max_date = daily_df['date_extract_parsed'].max()
        if pd.notna(max_date):
            sheet_updated = max_date.strftime('%d %b %Y')
    except Exception as e:
        logger.warning(f"Could not parse sheet update date: {e}")

    # Create gender map from TEAM DATA
    gender_map = {}
    for _, row in team_df.iterrows():
        strava_id = str(row.get('STRAVA_ID', '')).strip()
        gender = str(row.get('GENDER', '')).strip().upper()
        # Handle srM, srF, etc - just take first letter after 'sr'
        if gender.startswith('SR'):
            gender = gender[2] if len(gender) > 2 else gender
        gender = 'M' if gender == 'M' else 'F' if gender == 'F' else 'U'
        if strava_id:
            gender_map[strava_id] = gender

    daily_df['athlete_id'] = daily_df['ID'].astype(str).str.strip()
    daily_df['athlete_name'] = daily_df['Name'].astype(str).str.strip()
    daily_df['team'] = daily_df['TEAM_ID'].astype(str).str.strip()
    daily_df['points'] = pd.to_numeric(daily_df.get(
        'CalcTotal', 0), errors='coerce').fillna(0)
    daily_df['calc_run'] = pd.to_numeric(
        daily_df.get('CalcRun', 0), errors='coerce').fillna(0)
    daily_df['calc_walk'] = pd.to_numeric(
        daily_df.get('CalcWalk', 0), errors='coerce').fillna(0)
    daily_df['calc_ride'] = pd.to_numeric(
        daily_df.get('CalcRide', 0), errors='coerce').fillna(0)
    daily_df['gender'] = daily_df['athlete_id'].map(gender_map).fillna('U')
    daily_df = daily_df[daily_df['team'] != 'nan']

    # Overall athletes
    athlete_stats = daily_df.groupby(['athlete_name', 'athlete_id', 'team'])[
        'points'].sum().reset_index()
    athlete_stats.columns = ['name', 'athlete_id', 'team', 'points']
    athlete_list = athlete_stats.to_dict('records')

    # Gender-based leaderboards
    # Men Run/Walk
    men_df = daily_df[daily_df['gender'] == 'M'].copy()
    men_run_walk = men_df.groupby(['athlete_name', 'athlete_id']).agg({
        'calc_run': 'sum',
        'calc_walk': 'sum'
    }).reset_index()
    men_run_walk['points'] = men_run_walk['calc_run'] + \
        men_run_walk['calc_walk']
    men_run_walk = men_run_walk[men_run_walk['points']
                                > 0].sort_values('points', ascending=False)
    men_run_list = [{'name': row['athlete_name'], 'points': row['points']}
                    for _, row in men_run_walk.iterrows()]

    # Women Run/Walk
    women_df = daily_df[daily_df['gender'] == 'F'].copy()
    women_run_walk = women_df.groupby(['athlete_name', 'athlete_id']).agg({
        'calc_run': 'sum',
        'calc_walk': 'sum'
    }).reset_index()
    women_run_walk['points'] = women_run_walk['calc_run'] + \
        women_run_walk['calc_walk']
    women_run_walk = women_run_walk[women_run_walk['points'] > 0].sort_values(
        'points', ascending=False)
    women_run_list = [{'name': row['athlete_name'], 'points': row['points']}
                      for _, row in women_run_walk.iterrows()]

    # Men Ride
    men_ride = men_df.groupby(['athlete_name', 'athlete_id'])[
        'calc_ride'].sum().reset_index()
    men_ride = men_ride[men_ride['calc_ride'] >
                        0].sort_values('calc_ride', ascending=False)
    men_ride_list = [{'name': row['athlete_name'], 'points': row['calc_ride']}
                     for _, row in men_ride.iterrows()]

    # Women Ride
    women_ride = women_df.groupby(['athlete_name', 'athlete_id'])[
        'calc_ride'].sum().reset_index()
    women_ride = women_ride[women_ride['calc_ride'] >
                            0].sort_values('calc_ride', ascending=False)
    women_ride_list = [{'name': row['athlete_name'], 'points': row['calc_ride']}
                       for _, row in women_ride.iterrows()]

    # Teams
    teams_data = []
    for _, row in summary_df.iterrows():
        team = str(row.get('TEAM', row.get('TEAM ', ''))).strip()
        points = float(pd.to_numeric(
            row.get('POINT', 0), errors='coerce') or 0)
        if team and team != 'nan':
            teams_data.append({'team': team, 'points': points})

    if len(teams_data) == 0:
        team_totals = daily_df.groupby('team')['points'].sum().reset_index()
        for _, row in team_totals.iterrows():
            team = row['team']
            points = row['points']
            if team and team != 'nan':
                teams_data.append({'team': team, 'points': float(points)})

    return {
        'athletes': athlete_list,
        'teams': teams_data,
        'leaderboards': {
            'men_run': men_run_list,
            'women_run': women_run_list,
            'men_ride': men_ride_list,
            'women_ride': women_ride_list
        },
        'sheet_updated': sheet_updated
    }


def compute_team_details(daily_df, team_id):
    daily_df.columns = [str(c).strip() for c in daily_df.columns]

    daily_df['athlete_id'] = daily_df['ID'].astype(str).str.strip()
    daily_df['athlete_name'] = daily_df['Name'].astype(str).str.strip()
    daily_df['team'] = daily_df['TEAM_ID'].astype(str).str.strip()
    daily_df['calc_run'] = pd.to_numeric(
        daily_df.get('CalcRun', 0), errors='coerce').fillna(0)
    daily_df['calc_walk'] = pd.to_numeric(
        daily_df.get('CalcWalk', 0), errors='coerce').fillna(0)
    daily_df['calc_ride'] = pd.to_numeric(
        daily_df.get('CalcRide', 0), errors='coerce').fillna(0)
    daily_df['calc_total'] = pd.to_numeric(
        daily_df.get('CalcTotal', 0), errors='coerce').fillna(0)

    team_df = daily_df[daily_df['team'] == team_id].copy()
    if team_df.empty:
        return []

    members = []
    for athlete_id, group in team_df.groupby('athlete_id'):
        name = group['athlete_name'].iloc[0]
        run_walk = group['calc_run'].sum() + group['calc_walk'].sum()
        ride = group['calc_ride'].sum()
        total = group['calc_total'].sum()
        members.append({'name': name, 'run_walk_points': f"{run_walk:.1f}",
                       'ride_points': f"{ride:.1f}", 'total_points': f"{total:.1f}"})

    members.sort(key=lambda x: x['name'])
    return members


def compute_athlete_activities(daily_df, athlete_id):
    daily_df.columns = [str(c).strip() for c in daily_df.columns]

    daily_df['athlete_id'] = daily_df['ID'].astype(str).str.strip()
    daily_df['date_extract'] = pd.to_datetime(
        daily_df['DATE_EXTRACT'], errors='coerce')
    daily_df['calc_run'] = pd.to_numeric(
        daily_df.get('CalcRun', 0), errors='coerce').fillna(0)
    daily_df['calc_walk'] = pd.to_numeric(
        daily_df.get('CalcWalk', 0), errors='coerce').fillna(0)
    daily_df['calc_ride'] = pd.to_numeric(
        daily_df.get('CalcRide', 0), errors='coerce').fillna(0)

    athlete_df = daily_df[daily_df['athlete_id'] == athlete_id].copy()
    if athlete_df.empty:
        return {'dates': [], 'daily_activities': []}

    today = datetime.now(pytz.timezone(TIMEZONE)).date()
    date_range = pd.date_range(start=START_DATE, end=today, freq='D')
    date_labels = [d.strftime('%d/%m') for d in date_range]

    athlete_df['date_label'] = athlete_df['date_extract'].dt.strftime('%d/%m')

    daily_run = {}
    daily_walk = {}
    daily_ride = {}

    for _, row in athlete_df.iterrows():
        date_label = row['date_label']
        if pd.notna(date_label):
            daily_run[date_label] = daily_run.get(
                date_label, 0) + row['calc_run']
            daily_walk[date_label] = daily_walk.get(
                date_label, 0) + row['calc_walk']
            daily_ride[date_label] = daily_ride.get(
                date_label, 0) + row['calc_ride']

    activities = []

    if any(v > 0 for v in daily_run.values()):
        run_values = {d: daily_run.get(d, 0) if daily_run.get(
            d, 0) > 0 else '-' for d in date_labels}
        run_total = sum(v for v in run_values.values() if v != '-')
        run_active = sum(1 for v in run_values.values() if v != '-')
        activities.append({'type': 'Run', 'values': run_values,
                          'total': run_total, 'active_days': run_active})

    if any(v > 0 for v in daily_walk.values()):
        walk_values = {d: daily_walk.get(d, 0) if daily_walk.get(
            d, 0) > 0 else '-' for d in date_labels}
        walk_total = sum(v for v in walk_values.values() if v != '-')
        walk_active = sum(1 for v in walk_values.values() if v != '-')
        activities.append({'type': 'Walk', 'values': walk_values,
                          'total': walk_total, 'active_days': walk_active})

    if any(v > 0 for v in daily_ride.values()):
        ride_values = {d: daily_ride.get(d, 0) if daily_ride.get(
            d, 0) > 0 else '-' for d in date_labels}
        ride_total = sum(v for v in ride_values.values() if v != '-')
        ride_active = sum(1 for v in ride_values.values() if v != '-')
        activities.append({'type': 'Ride', 'values': ride_values,
                          'total': ride_total, 'active_days': ride_active})

    return {'dates': date_labels, 'daily_activities': activities}


@app.route('/')
def index():
    return render_template_string(MAIN_TEMPLATE)


@app.route('/api/data')
def api_data():
    try:
        creds = load_service_account_credentials()
        if not creds:
            return jsonify({'error': 'No credentials available'}), 500

        daily_df = read_google_sheet(creds, 'DAILY-UPDATE')
        summary_df = read_google_sheet(creds, 'SUMMARY')
        team_df = read_google_sheet(creds, 'TEAM DATA')

        if daily_df.empty or summary_df.empty or team_df.empty:
            return jsonify({'error': 'Sheets are empty'}), 500

        results = compute_main_data(daily_df, summary_df, team_df)
        tz = pytz.timezone(TIMEZONE)
        payload = {
            'athletes': results['athletes'],
            'teams': results['teams'],
            'leaderboards': results['leaderboards'],
            'sheet_updated': results['sheet_updated'],
            'loaded_at': datetime.now(tz).isoformat()
        }
        return jsonify(payload)
    except Exception as e:
        logger.exception("Failed to build API data: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/team/<team_id>')
def team_detail(team_id):
    try:
        creds = load_service_account_credentials()
        if not creds:
            return "No credentials available", 500

        daily_df = read_google_sheet(creds, 'DAILY-UPDATE')
        if daily_df.empty:
            return "No data available", 500

        members = compute_team_details(daily_df, team_id)
        total_points = sum(float(m['total_points']) for m in members)
        tz = pytz.timezone(TIMEZONE)
        updated_at = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

        return render_template_string(TEAM_TEMPLATE, team_id=team_id, members=members,
                                      member_count=len(members), total_points=f"{total_points:.1f}",
                                      updated_at=updated_at)
    except Exception as e:
        logger.exception("Failed to load team details: %s", e)
        return f"Error: {str(e)}", 500


@app.route('/api/athlete/<athlete_id>')
def athlete_activities(athlete_id):
    try:
        creds = load_service_account_credentials()
        if not creds:
            return jsonify({'error': 'No credentials available'}), 500

        daily_df = read_google_sheet(creds, 'DAILY-UPDATE')
        if daily_df.empty:
            return jsonify({'error': 'No data available'}), 500

        result = compute_athlete_activities(daily_df, athlete_id)
        return jsonify(result)
    except Exception as e:
        logger.exception("Failed to load athlete activities: %s", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
