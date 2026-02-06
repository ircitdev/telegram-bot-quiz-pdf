from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import get_all_inner_roles
import uvicorn
import os

app = FastAPI()

if not os.path.exists("templates"):
    os.makedirs("templates")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Навигатор: Внутреннее состояние</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/wordcloud2.js/1.2.2/wordcloud2.min.js"></script>
    <style>
        body { background-color: #0f172a; color: #ffffff; font-family: sans-serif; overflow: hidden; }
        #canvas-container { width: 100vw; height: 100vh; display: flex; justify-content: center; align-items: center; }
        h1 { position: absolute; top: 20px; left: 20px; color: #fbbf24; opacity: 0.5; }
    </style>
</head>
<body>
    <h1>ВНУТРЕННЕЕ СОСТОЯНИЕ ГРУППЫ</h1>
    <div id="canvas-container">
        <canvas id="word-cloud" width="1024" height="768"></canvas>
    </div>

    <script>
        const canvas = document.getElementById('word-cloud');
        
        function processWords(words) {
            const counts = {};
            words.forEach(function(x) { counts[x] = (counts[x] || 0) + 1; });
            return Object.keys(counts).map(key => [key, 15 + (counts[key] * 10)]);
        }

        function loadData() {
            fetch('/api/words')
                .then(response => response.json())
                .then(data => {
                    const list = processWords(data);
                    WordCloud(canvas, { 
                        list: list,
                        gridSize: 16,
                        weightFactor: 1.2,
                        fontFamily: 'Roboto, sans-serif',
                        color: function() {
                            const colors = ['#fbbf24', '#38bdf8', '#ffffff', '#94a3b8'];
                            return colors[Math.floor(Math.random() * colors.length)];
                        },
                        backgroundColor: '#0f172a'
                    });
                });
        }

        loadData();
        setInterval(loadData, 5000);
        
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    </script>
</body>
</html>
"""

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(HTML_TEMPLATE)

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/words")
async def get_words():
    words = await get_all_inner_roles(limit=100)
    return words

def start_web():
    uvicorn.run(app, host="0.0.0.0", port=8000)
