from flask import Flask, jsonify
from flask_cors import CORS
from flask_sock import Sock
import json
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "allow_headers": "*",
        "expose_headers": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "supports_credentials": True
    }
})
sock = Sock(app)
sock.init_app(app)

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/v1/services/health', methods=['GET'])
def services_health():
    try:
        return jsonify({
            "status": "ok",
            "all_healthy": True,
            "services": {
                "telegram_client": {
                    "status": "running",
                    "running": True,
                    "healthy": True,
                    "uptime": 1200,
                    "last_error": None
                },
                "database": {
                    "status": "running",
                    "running": True,
                    "healthy": True,
                    "uptime": 3600,
                    "last_error": None
                },
                "api_server": {
                    "status": "running",
                    "running": True,
                    "healthy": True,
                    "uptime": 600,
                    "last_error": None
                },
                "message_handler": {
                    "status": "running",
                    "running": True,
                    "healthy": True,
                    "uptime": 300,
                    "last_error": None
                }
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@sock.route('/api/logs')
def logs_socket(ws):
    try:
        while True:
            message = {
                "type": "log",
                "level": "info",
                "message": "Test log mesajı",
                "timestamp": datetime.now().isoformat()
            }
            ws.send(json.dumps(message))
    except Exception as e:
        print(f"WebSocket hatası: {e}")
        if not ws.closed:
            ws.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True) 