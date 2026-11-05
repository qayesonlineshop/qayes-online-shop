import os, sqlite3, uuid
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string
from werkzeug.utils import secure_filename

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(ROOT / "static" / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
DB = os.environ.get("DATABASE_PATH", str(ROOT / "qayes.db"))
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")
ALLOWED = {"jpg", "jpeg", "png", "webp", "gif"}

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT DEFAULT '',
        description TEXT DEFAULT '', price_bdt REAL NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0, image_url TEXT DEFAULT '', active INTEGER DEFAULT 1)""")
        c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        defaults = {"shop_name":"Qayes Online Shop","delivery_charge_bdt":"60",
                    "card_enabled":"1","bkash_enabled":"1","nagad_enabled":"1","cod_enabled":"1"}
        for k,v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))

def settings():
    with db() as c:
        return {r["key"]:r["value"] for r in c.execute("SELECT key,value FROM settings")}

def save_image(f):
    if not f or not f.filename:
        return ""
    ext = f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED:
        raise ValueError("ছবি JPG, PNG, WEBP অথবা GIF হতে হবে।")
    name = secure_filename(Path(f.filename).stem)[:35] or "product"
    filename = f"{name}-{uuid.uuid4().hex[:10]}.{ext}"
    f.save(UPLOAD_DIR / filename)
    return "/static/uploads/" + filename

def authorized():
    return ADMIN_KEY != "change-me" and request.headers.get("X-Admin-Key","") == ADMIN_KEY

@app.get("/")
def home():
    return jsonify(name="Qayes Online Shop API",status="running",currency="BDT")

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/api/v1/products")
def products():
    with db() as c:
        rows = c.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall()
    return jsonify(items=[dict(r) for r in rows])

@app.get("/api/v1/settings")
def public_settings():
    s=settings()
    return jsonify({k:s.get(k) for k in ("shop_name","delivery_charge_bdt","card_enabled","bkash_enabled","nagad_enabled","cod_enabled")})

@app.post("/api/v1/admin/products")
def api_add_product():
    if not authorized():
        return jsonify(error="Unauthorized"),401
    d=request.form if request.form else (request.get_json(silent=True) or {})
    try:
        image_url=str(d.get("image_url","")).strip()
        if request.files.get("image"):
            image_url=save_image(request.files["image"])
        name=str(d.get("name","")).strip()
        if not name:
            return jsonify(error="Product name is required"),400
        with db() as c:
            cur=c.execute("INSERT INTO products(name,category,description,price_bdt,stock,image_url) VALUES(?,?,?,?,?,?)",
                (name,d.get("category",""),d.get("description",""),float(d.get("price_bdt",0)),int(d.get("stock",0)),image_url))
        return jsonify(ok=True,id=cur.lastrowid,image_url=image_url),201
    except ValueError as e:
        return jsonify(error=str(e)),400

@app.put("/api/v1/admin/products/<int:pid>")
def edit_product(pid):
    if not authorized(): return jsonify(error="Unauthorized"),401
    d=request.get_json(silent=True) or {}
    fields=[k for k in ("name","category","description","price_bdt","stock","image_url","active") if k in d]
    if fields:
        with db() as c:
            c.execute("UPDATE products SET "+",".join(k+"=?" for k in fields)+" WHERE id=?",
                      [d[k] for k in fields]+[pid])
    return jsonify(ok=True)

@app.delete("/api/v1/admin/products/<int:pid>")
def delete_product(pid):
    if not authorized(): return jsonify(error="Unauthorized"),401
    with db() as c: c.execute("UPDATE products SET active=0 WHERE id=?",(pid,))
    return jsonify(ok=True)

@app.route("/admin",methods=["GET","POST"])
def admin():
    msg=""
    key=request.form.get("admin_key","")
    if request.method=="POST":
        action=request.form.get("action","")
        if key != ADMIN_KEY or ADMIN_KEY=="change-me":
            msg="Admin Key ভুল অথবা Render-এ ADMIN_KEY সেট করা নেই।"
        elif action=="settings":
            values={"shop_name":request.form.get("shop_name","Qayes Online Shop"),
                    "delivery_charge_bdt":request.form.get("delivery_charge_bdt","60"),
                    "card_enabled":"1" if request.form.get("card_enabled") else "0",
                    "bkash_enabled":"1" if request.form.get("bkash_enabled") else "0",
                    "nagad_enabled":"1" if request.form.get("nagad_enabled") else "0",
                    "cod_enabled":"1" if request.form.get("cod_enabled") else "0"}
            with db() as c:
                for k,v in values.items(): c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(k,v))
            msg="Shop Settings সংরক্ষণ হয়েছে।"
        elif action=="add":
            try:
                image_url=request.form.get("image_url","").strip()
                if request.files.get("image"): image_url=save_image(request.files["image"])
                name=request.form.get("name","").strip()
                if not name: raise ValueError("পণ্যের নাম দিন।")
                with db() as c:
                    c.execute("INSERT INTO products(name,category,description,price_bdt,stock,image_url) VALUES(?,?,?,?,?,?)",
                    (name,request.form.get("category",""),request.form.get("description",""),
                     float(request.form.get("price_bdt",0)),int(request.form.get("stock",0)),image_url))
                msg="পণ্য যোগ হয়েছে।"
            except ValueError as e: msg=str(e)
    s=settings()
    with db() as c: rows=c.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall()
    html=r"""
<!doctype html><html lang="bn"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qayes Online Shop Admin</title><style>
body{font-family:Arial,sans-serif;background:#f3f5f7;margin:0;padding:14px;color:#222}
.box{background:white;padding:16px;border-radius:12px;margin:12px 0}input,textarea{box-sizing:border-box;width:100%;padding:11px;border:1px solid #bbb;border-radius:6px}
label{display:block;margin:10px 0 5px}button{background:#111;color:white;border:0;padding:11px 15px;border-radius:7px;margin-top:10px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.check{display:flex;align-items:center;gap:8px}.check input{width:auto}
.msg{background:#e4f6e7;padding:10px;border-radius:6px}.hint{font-size:13px;color:#555}.item{border-top:1px solid #ddd;padding:12px 0}
.item img{width:110px;height:110px;object-fit:contain;background:#f5f5f5}
</style><h2>Qayes Online Shop — Admin</h2>
{% if msg %}<p class="msg">{{msg}}</p>{% endif %}
<div class="box"><form method="post" enctype="multipart/form-data">
<label>Admin Key</label><input type="password" name="admin_key" value="{{key}}" required>
<h3>Shop Settings</h3><label>Shop Name</label><input name="shop_name" value="{{s.get('shop_name','Qayes Online Shop')}}">
<label>Delivery Charge (BDT)</label><input name="delivery_charge_bdt" type="number" min="0" value="{{s.get('delivery_charge_bdt','60')}}">
<div class="grid">
<label class="check"><input type="checkbox" name="card_enabled" {% if s.get('card_enabled','1')=='1' %}checked{% endif %}> Card</label>
<label class="check"><input type="checkbox" name="bkash_enabled" {% if s.get('bkash_enabled','1')=='1' %}checked{% endif %}> bKash</label>
<label class="check"><input type="checkbox" name="nagad_enabled" {% if s.get('nagad_enabled','1')=='1' %}checked{% endif %}> Nagad</label>
<label class="check"><input type="checkbox" name="cod_enabled" {% if s.get('cod_enabled','1')=='1' %}checked{% endif %}> Cash on Delivery</label></div>
<button name="action" value="settings">Save Settings</button></form></div>
<div class="box"><h3>Add Product</h3><form method="post" enctype="multipart/form-data">
<input type="hidden" name="admin_key" value="{{key}}">
<label>Product Name</label><input name="name" required><label>Category</label><input name="category">
<label>Description</label><textarea name="description" rows="3"></textarea>
<div class="grid"><div><label>Price (BDT)</label><input name="price_bdt" type="number" min="0" step="0.01" required></div>
<div><label>Stock</label><input name="stock" type="number" min="0" value="0" required></div></div>
<label>মোবাইল গ্যালারি থেকে পণ্যের ছবি বাছুন</label><input type="file" name="image" accept="image/png,image/jpeg,image/webp,image/gif">
<p class="hint">সর্বোচ্চ 5 MB · JPG, PNG, WEBP বা GIF</p>
<label>অথবা Image URL</label><input name="image_url" placeholder="https://...">
<button name="action" value="add">Add Product</button></form></div>
<div class="box"><h3>Products ({{rows|length}})</h3>{% for p in rows %}<div class="item">
{% if p['image_url'] %}<img src="{{p['image_url']}}" alt="product"><br>{% endif %}
<strong>{{p['name']}}</strong><br>৳{{p['price_bdt']}} · Stock: {{p['stock']}}</div>{% else %}No products yet{% endfor %}</div>
</html>"""
    return render_template_string(html,msg=msg,key=key,s=s,rows=rows)

init()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
