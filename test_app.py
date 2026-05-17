from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def hello():
    return f"<h1>Hello from Render!</h1><p>PORT={os.environ.get('PORT', 'not set')}</p>"

@app.route("/health")
def health():
    return jsonify({"status": "ok", "port": os.environ.get("PORT")})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
