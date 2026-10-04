import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify({
        "name": "Qayes Online Shop API",
        "status": "running",
        "currency": "BDT"
    })

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.get("/api/v1/products")
def products():
    return jsonify({"items": [
        {"id": 1, "name": "Sample Product", "price_bdt": 500, "stock": 10, "currency": "BDT"}
    ]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
