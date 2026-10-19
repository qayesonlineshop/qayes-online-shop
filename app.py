import os
import sqlite3
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

DB_PATH = os.environ.get("DATABASE_PATH", "qayes.db")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                description TEXT DEFAULT '',
                price_bdt REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0,
                image_url TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        defaults = {
            "shop_name": "Qayes Online Shop",
            "delivery_charge_bdt": "60",
            "card_enabled": "1",
            "bkash_enabled": "1",
            "nagad_enabled": "1",
            "cod_enabled": "1",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )


def is_admin():
    supplied = request.headers.get("X-Admin-Key", "")
    if not supplied:
        supplied = request.args.get("admin_key", "")
    if not supplied:
        supplied = request.form.get("admin_key", "")
    if not supplied and request.is_json:
        supplied = (request.get_json(silent=True) or {}).get("admin_key", "")
    return bool(ADMIN_KEY) and supplied == ADMIN_KEY


def settings_dict():
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    result = {row["key"]: row["value"] for row in rows}
    for key in ("card_enabled", "bkash_enabled", "nagad_enabled", "cod_enabled"):
        result[key] = result.get(key, "1") == "1"
    try:
        result["delivery_charge_bdt"] = float(result.get("delivery_charge_bdt", "60"))
    except (TypeError, ValueError):
        result["delivery_charge_bdt"] = 60
    return result


def product_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"] or "",
        "description": row["description"] or "",
        "price_bdt": float(row["price_bdt"] or 0),
        "stock": int(row["stock"] or 0),
        "image_url": row["image_url"] or "",
        "active": bool(row["active"]),
        "currency": "BDT",
    }


def read_payload():
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    return request.form.to_dict()


@app.get("/")
def home():
    return jsonify({
        "name": "Qayes Online Shop API",
        "status": "running",
        "currency": "BDT",
        "admin": "/admin",
        "products": "/api/v1/products",
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/v1/products")
def list_products():
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE active = 1 ORDER BY id DESC"
        ).fetchall()
    return jsonify({"items": [product_dict(row) for row in rows], "currency": "BDT"})


@app.get("/api/v1/categories")
def list_categories():
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM products WHERE active = 1 "
            "AND category != '' ORDER BY category"
        ).fetchall()
    return jsonify({"items": [row["category"] for row in rows]})


@app.get("/api/v1/settings")
def public_settings():
    return jsonify(settings_dict())


@app.get("/api/v1/admin/settings")
def admin_get_settings():
    if not is_admin():
        return jsonify({"error": "Unauthorized. Check Admin Key."}), 401
    return jsonify(settings_dict())


@app.put("/api/v1/admin/settings")
@app.post("/api/v1/admin/settings")
def admin_save_settings():
    if not is_admin():
        return jsonify({"error": "Unauthorized. Check Admin Key."}), 401
    data = read_payload()
    allowed = {
        "shop_name", "delivery_charge_bdt",
        "card_enabled", "bkash_enabled", "nagad_enabled", "cod_enabled",
    }
    with connect() as conn:
        for key in allowed:
            if key not in data:
                continue
            value = data[key]
            if key.endswith("_enabled"):
                value = "1" if str(value).lower() in ("1", "true", "yes", "on") else "0"
            elif key == "delivery_charge_bdt":
                try:
                    value = str(max(0, float(value)))
                except (TypeError, ValueError):
                    return jsonify({"error": "Delivery charge must be a number."}), 400
            else:
                value = str(value).strip()[:120]
            conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
    return jsonify({"ok": True, "settings": settings_dict()})


@app.post("/api/v1/admin/products")
def admin_add_product():
    if not is_admin():
        return jsonify({"error": "Unauthorized. Check Admin Key."}), 401
    data = read_payload()

    # Accept both JSON requests and standard HTML form submissions.
    name = str(data.get("name") or data.get("product_name") or "").strip()
    if not name:
        return jsonify({"error": "Product name is required. Enter a product name."}), 400

    category = str(data.get("category") or "").strip()
    description = str(data.get("description") or "").strip()
    image_url = str(data.get("image_url") or data.get("image") or "").strip()

    try:
        price = float(data.get("price_bdt", data.get("price", 0)) or 0)
        stock = int(float(data.get("stock", 0) or 0))
        if price < 0 or stock < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Price and stock must be valid non-negative numbers."}), 400

    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO products
               (name, category, description, price_bdt, stock, image_url, active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (name, category, description, price, stock, image_url),
        )
        product_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return jsonify({"ok": True, "item": product_dict(row)}), 201


@app.put("/api/v1/admin/products/<int:product_id>")
def admin_edit_product(product_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized. Check Admin Key."}), 401
    data = read_payload()
    with connect() as conn:
        old = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if old is None:
            return jsonify({"error": "Product not found."}), 404

        name = str(data.get("name", old["name"]) or "").strip()
        if not name:
            return jsonify({"error": "Product name is required."}), 400
        category = str(data.get("category", old["category"] or "") or "").strip()
        description = str(data.get("description", old["description"] or "") or "").strip()
        image_url = str(data.get("image_url", old["image_url"] or "") or "").strip()
        try:
            price = float(data.get("price_bdt", old["price_bdt"]) or 0)
            stock = int(float(data.get("stock", old["stock"]) or 0))
            if price < 0 or stock < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Price and stock must be valid non-negative numbers."}), 400

        conn.execute(
            """UPDATE products
               SET name=?, category=?, description=?, price_bdt=?, stock=?, image_url=?
               WHERE id=?""",
            (name, category, description, price, stock, image_url, product_id),
        )
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return jsonify({"ok": True, "item": product_dict(row)})


@app.delete("/api/v1/admin/products/<int:product_id>")
def admin_delete_product(product_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized. Check Admin Key."}), 401
    with connect() as conn:
        cursor = conn.execute("UPDATE products SET active=0 WHERE id=?", (product_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Product not found."}), 404
    return jsonify({"ok": True})


ADMIN_HTML = r"""
<!doctype html>
<html lang="bn">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qayes Online Shop — Admin</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#222;font:16px Arial,sans-serif}
main{max-width:850px;margin:auto;padding:14px}h2{font-size:22px}
.card{background:#fff;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 1px 4px #ddd}
label{display:block;margin:10px 0 5px;font-weight:600;font-size:14px}
input,textarea{width:100%;padding:12px;border:1px solid #bbb;border-radius:6px;font-size:16px}
button{background:#111;color:white;border:0;border-radius:6px;padding:11px 15px;margin-top:10px;font-size:15px}
.checkrow{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee}
.checkrow input{width:22px;height:22px}.muted{color:#666;font-size:13px}
.item{display:flex;gap:12px;border-top:1px solid #eee;padding:12px 0;align-items:flex-start}
.item img{width:78px;height:78px;object-fit:cover;border-radius:6px;background:#eee}
.item .details{flex:1;min-width:0;overflow-wrap:anywhere}.item button{margin-right:5px}
#notice{padding:10px;border-radius:6px;margin-top:10px;display:none}
</style>
</head>
<body><main>
<h2>Qayes Online Shop — Admin</h2>
<div class="card">
<label for="adminKey">Admin Key</label>
<input id="adminKey" type="password" autocomplete="off" placeholder="Render-এর ADMIN_KEY লিখুন">
<button onclick="refreshAll()">Refresh</button>
<div class="muted">Admin Key কাউকে পাঠাবেন না।</div>
<div id="notice"></div>
</div>

<div class="card">
<h3>Shop Settings</h3>
<label for="shopName">Shop Name</label><input id="shopName" value="Qayes Online Shop">
<label for="delivery">Delivery Charge (BDT)</label><input id="delivery" type="number" min="0" value="60">
<div class="checkrow"><span>Card</span><input id="card" type="checkbox" checked></div>
<div class="checkrow"><span>bKash</span><input id="bkash" type="checkbox" checked></div>
<div class="checkrow"><span>Nagad</span><input id="nagad" type="checkbox" checked></div>
<div class="checkrow"><span>Cash on Delivery</span><input id="cod" type="checkbox" checked></div>
<button onclick="saveSettings()">Save Settings</button>
<p class="muted">কার্ড/bKash/Nagad পেমেন্ট চালু করতে আলাদা অনুমোদিত payment gateway লাগবে।</p>
</div>

<div class="card">
<h3 id="productTitle">Add Product</h3>
<input id="productId" type="hidden">
<label for="name">Product Name *</label><input id="name" placeholder="যেমন: হলুদের গুঁড়া">
<label for="category">Category</label><input id="category" placeholder="যেমন: মসলা">
<label for="description">Description</label><textarea id="description" rows="3" placeholder="পণ্যের বিবরণ"></textarea>
<label for="price">Price (BDT)</label><input id="price" type="number" min="0" step="0.01" value="0">
<label for="stock">Stock</label><input id="stock" type="number" min="0" step="1" value="0">
<label for="imageUrl">Image URL (optional)</label><input id="imageUrl" type="url" placeholder="https://...">
<button onclick="saveProduct()">Save Product</button>
<button onclick="clearProduct()" style="background:#666">Clear</button>
</div>

<div class="card"><h3>Products</h3><div id="products">Loading…</div></div>
</main>
<script>
const $ = id => document.getElementById(id);
function key(){return $('adminKey').value.trim();}
function headers(){return {'Content-Type':'application/json','X-Admin-Key':key()};}
function notice(message, bad=false){
  const n=$('notice'); n.style.display='block'; n.style.background=bad?'#ffe3e3':'#e0f7e8';
  n.style.color=bad?'#8b0000':'#075b2a'; n.textContent=message;
}
async function api(url, options={}){
  const response=await fetch(url,{...options,headers:{...headers(),...(options.headers||{})}});
  let data={}; try{data=await response.json();}catch(e){}
  if(!response.ok) throw new Error(data.error || ('Request failed: '+response.status));
  return data;
}
async function refreshAll(){
  if(!key()){notice('আগে Admin Key লিখুন।',true);return;}
  try{
    const s=await api('/api/v1/admin/settings');
    $('shopName').value=s.shop_name || 'Qayes Online Shop';
    $('delivery').value=s.delivery_charge_bdt ?? 60;
    $('card').checked=!!s.card_enabled; $('bkash').checked=!!s.bkash_enabled;
    $('nagad').checked=!!s.nagad_enabled; $('cod').checked=!!s.cod_enabled;
    await loadProducts(); notice('Settings ও Products লোড হয়েছে।');
  }catch(e){notice(e.message,true);}
}
async function saveSettings(){
  if(!key()){notice('আগে Admin Key লিখুন।',true);return;}
  try{
    await api('/api/v1/admin/settings',{method:'PUT',body:JSON.stringify({
      shop_name:$('shopName').value,delivery_charge_bdt:$('delivery').value,
      card_enabled:$('card').checked,bkash_enabled:$('bkash').checked,
      nagad_enabled:$('nagad').checked,cod_enabled:$('cod').checked
    })});
    notice('Shop Settings সংরক্ষণ হয়েছে।');
  }catch(e){notice(e.message,true);}
}
async function saveProduct(){
  if(!key()){notice('আগে Admin Key লিখুন।',true);return;}
  const payload={name:$('name').value,category:$('category').value,
    description:$('description').value,price_bdt:$('price').value,
    stock:$('stock').value,image_url:$('imageUrl').value};
  try{
    const id=$('productId').value;
    if(id) await api('/api/v1/admin/products/'+id,{method:'PUT',body:JSON.stringify(payload)});
    else await api('/api/v1/admin/products',{method:'POST',body:JSON.stringify(payload)});
    clearProduct(); await loadProducts(); notice(id?'Product updated.':'Product added successfully.');
  }catch(e){notice(e.message,true);}
}
function clearProduct(){
  $('productId').value=''; $('productTitle').textContent='Add Product';
  $('name').value=''; $('category').value=''; $('description').value='';
  $('price').value='0'; $('stock').value='0'; $('imageUrl').value='';
}
async function loadProducts(){
  const data=await api('/api/v1/products');
  const list=data.items||[];
  if(!list.length){$('products').innerHTML='<p>No products yet</p>';return;}
  $('products').innerHTML=list.map(p=>`<div class="item">
    ${p.image_url?`<img src="${escapeHtml(p.image_url)}" alt="" onerror="this.style.display='none'">`:'<div style="width:78px;height:78px;background:#eee;border-radius:6px"></div>'}
    <div class="details"><b>${escapeHtml(p.name)}</b><br>৳${Number(p.price_bdt).toFixed(2)} · Stock: ${p.stock}
    <br><span class="muted">${escapeHtml(p.category||'')}</span><br>
    <button onclick="editProduct(${p.id})">Edit</button>
    <button onclick="deleteProduct(${p.id})" style="background:#a40000">Delete</button></div></div>`).join('');
}
function escapeHtml(value){
 return String(value??'').replace(/[&<>"']/g, ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
async function editProduct(id){
 try{
  const data=await api('/api/v1/products');const p=(data.items||[]).find(x=>x.id===id);
  if(!p) throw new Error('Product not found');
  $('productId').value=p.id;$('productTitle').textContent='Edit Product';
  $('name').value=p.name;$('category').value=p.category;$('description').value=p.description;
  $('price').value=p.price_bdt;$('stock').value=p.stock;$('imageUrl').value=p.image_url;
  window.scrollTo({top:0,behavior:'smooth'});
 }catch(e){notice(e.message,true);}
}
async function deleteProduct(id){
 if(!confirm('এই পণ্যটি মুছবেন?'))return;
 try{await api('/api/v1/admin/products/'+id,{method:'DELETE'});await loadProducts();notice('Product deleted.');}
 catch(e){notice(e.message,true);}
}
</script></body></html>
"""


@app.get("/admin")
def admin_page():
    return render_template_string(ADMIN_HTML)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
