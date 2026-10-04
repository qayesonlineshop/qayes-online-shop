import os, sqlite3
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB = "qayes.db"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-this-key")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT DEFAULT '',
        description TEXT DEFAULT '',
        price_bdt INTEGER NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0,
        image_url TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    defaults = {
        "shop_name":"Qayes Online Shop",
        "delivery_charge_bdt":"60",
        "card_enabled":"1",
        "bkash_enabled":"1",
        "nagad_enabled":"1",
        "cod_enabled":"1"
    }
    for k,v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
    c.commit(); c.close()

def admin_ok():
    return request.headers.get("X-Admin-Key","") == ADMIN_KEY

@app.get("/")
def home():
    return jsonify({"name":"Qayes Online Shop","status":"running","currency":"BDT"})

@app.get("/health")
def health():
    return jsonify({"status":"ok"})

@app.get("/api/v1/settings")
def get_settings():
    c=db()
    rows=c.execute("SELECT key,value FROM settings").fetchall()
    c.close()
    return jsonify({r["key"]: r["value"] for r in rows})

@app.put("/api/v1/settings")
def update_settings():
    if not admin_ok(): return jsonify({"error":"Unauthorized"}),401
    data=request.get_json(silent=True) or {}
    c=db()
    for k,v in data.items():
        if k in {"shop_name","delivery_charge_bdt","card_enabled","bkash_enabled","nagad_enabled","cod_enabled"}:
            c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(k,str(v)))
    c.commit(); c.close()
    return get_settings()

@app.get("/api/v1/products")
def products():
    c=db()
    rows=c.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall()
    c.close()
    return jsonify({"items":[dict(r) for r in rows]})

@app.post("/api/v1/products")
def add_product():
    if not admin_ok(): return jsonify({"error":"Unauthorized"}),401
    d=request.get_json(silent=True) or {}
    if not d.get("name"): return jsonify({"error":"name is required"}),400
    c=db()
    cur=c.execute("""INSERT INTO products(name,category,description,price_bdt,stock,image_url,active)
                     VALUES(?,?,?,?,?,?,?)""",
                  (d["name"],d.get("category",""),d.get("description",""),
                   int(d.get("price_bdt",0)),int(d.get("stock",0)),
                   d.get("image_url",""),1))
    c.commit(); pid=cur.lastrowid; c.close()
    return jsonify({"id":pid,"message":"Product added"}),201

@app.put("/api/v1/products/<int:pid>")
def edit_product(pid):
    if not admin_ok(): return jsonify({"error":"Unauthorized"}),401
    d=request.get_json(silent=True) or {}
    c=db()
    c.execute("""UPDATE products SET name=?,category=?,description=?,price_bdt=?,stock=?,image_url=?,active=?
                 WHERE id=?""",
              (d.get("name",""),d.get("category",""),d.get("description",""),
               int(d.get("price_bdt",0)),int(d.get("stock",0)),d.get("image_url",""),
               int(d.get("active",1)),pid))
    c.commit(); c.close()
    return jsonify({"message":"Product updated"})

@app.delete("/api/v1/products/<int:pid>")
def delete_product(pid):
    if not admin_ok(): return jsonify({"error":"Unauthorized"}),401
    c=db(); c.execute("DELETE FROM products WHERE id=?",(pid,)); c.commit(); c.close()
    return jsonify({"message":"Product deleted"})

ADMIN_HTML = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qayes Admin</title><style>
body{font-family:Arial;max-width:850px;margin:auto;padding:16px;background:#f5f6f8}
.card{background:white;padding:16px;margin:12px 0;border-radius:12px;box-shadow:0 2px 8px #ddd}
input,textarea{width:100%;box-sizing:border-box;padding:10px;margin:5px 0 10px;border:1px solid #ccc;border-radius:8px}
button{padding:10px 14px;border:0;border-radius:8px;background:#111;color:white}
label{display:block;margin:9px 0} h1{margin-bottom:5px}
</style></head><body>
<h1>Qayes Online Shop — Admin</h1>
<div class="card"><label>Admin Key<input id="key" type="password"></label>
<label>Shop Name<input id="shop"></label>
<label>Delivery Charge (BDT)<input id="delivery" type="number"></label>
<label><input id="card" type="checkbox" style="width:auto"> Card</label>
<label><input id="bkash" type="checkbox" style="width:auto"> bKash</label>
<label><input id="nagad" type="checkbox" style="width:auto"> Nagad</label>
<label><input id="cod" type="checkbox" style="width:auto"> Cash on Delivery</label>
<button onclick="saveSettings()">Save Settings</button></div>
<div class="card"><h3>Add Product</h3>
<input id="name" placeholder="Product name"><input id="cat" placeholder="Category">
<textarea id="desc" placeholder="Description"></textarea>
<input id="price" type="number" placeholder="Price in BDT"><input id="stock" type="number" placeholder="Stock">
<input id="img" placeholder="Image URL"><button onclick="addProduct()">Add Product</button></div>
<div class="card"><h3>Products</h3><div id="list">Loading...</div></div>
<script>
const key=()=>document.getElementById('key').value;
async function load(){
 let s=await fetch('/api/v1/settings').then(r=>r.json());
 shop.value=s.shop_name; delivery.value=s.delivery_charge_bdt;
 card.checked=s.card_enabled==='1'; bkash.checked=s.bkash_enabled==='1';
 nagad.checked=s.nagad_enabled==='1'; cod.checked=s.cod_enabled==='1';
 let p=await fetch('/api/v1/products').then(r=>r.json());
 list.innerHTML=p.items.map(x=>`<p><b>${x.name}</b> — ৳${x.price_bdt} — Stock: ${x.stock}</p>`).join('')||'No products yet';
}
async function saveSettings(){
 await fetch('/api/v1/settings',{method:'PUT',headers:{'Content-Type':'application/json','X-Admin-Key':key()},
 body:JSON.stringify({shop_name:shop.value,delivery_charge_bdt:delivery.value,card_enabled:card.checked?'1':'0',
 bkash_enabled:bkash.checked?'1':'0',nagad_enabled:nagad.checked?'1':'0',cod_enabled:cod.checked?'1':'0'})});
 alert('Settings saved'); load();
}
async function addProduct(){
 await fetch('/api/v1/products',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Key':key()},
 body:JSON.stringify({name:name.value,category:cat.value,description:desc.value,price_bdt:price.value,stock:stock.value,image_url:img.value})});
 alert('Product added'); load();
}
load();
</script></body></html>"""

@app.get("/admin")
def admin():
    return render_template_string(ADMIN_HTML)

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","10000")))
