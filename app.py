import os, sqlite3
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB = os.environ.get("DATABASE_PATH", "qayes.db")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "CHANGE_ME")

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
        price_bdt INTEGER NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        image_url TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1
    )""")
    c.commit()
    c.close()

init_db()

def auth():
    return request.headers.get("X-Admin-Key") == ADMIN_KEY

HTML = """<!doctype html><html lang="bn"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qayes Online Shop Admin</title>
<style>
body{font-family:Arial;background:#f5f6f8;padding:16px}
.card{background:#fff;padding:16px;margin:12px 0;border-radius:12px}
input,textarea{width:100%;box-sizing:border-box;padding:10px;margin:5px 0}
button{padding:9px 13px;margin:3px;border:0;border-radius:7px;background:#111;color:#fff}
.edit{background:#1565c0}.del{background:#c62828}.small{color:#666;font-size:13px}
</style></head><body>
<h2>Qayes Online Shop — Admin</h2>
<div class="card"><b>Admin Key</b>
<input id="key" type="password" placeholder="ADMIN_KEY">
<button onclick="load()">Refresh Products</button></div>
<div class="card"><h3 id="title">Add Product</h3>
<input id="name" placeholder="পণ্যের নাম"><input id="cat" placeholder="ক্যাটাগরি">
<textarea id="desc" placeholder="বর্ণনা"></textarea>
<input id="price" type="number" placeholder="দাম (BDT)">
<input id="stock" type="number" placeholder="স্টক">
<input id="img" placeholder="ছবির URL (ঐচ্ছিক)">
<button id="save" onclick="save()">Add Product</button>
<button id="cancel" style="display:none" onclick="cancelEdit()">Cancel</button></div>
<div class="card"><h3>Products</h3><div id="list">Refresh চাপুন</div></div>
<script>
let eid=null;
const $=id=>document.getElementById(id);
function load(){
 fetch('/api/v1/products').then(r=>r.json()).then(d=>{
  $('list').innerHTML=d.items.length?d.items.map(p=>'<div style="padding:10px;border-top:1px solid #ddd"><b>'+esc(p.name)+'</b> — ৳'+p.price_bdt+' — Stock: '+p.stock+'<br><span class="small">'+esc(p.category)+'</span><br><button class="edit" onclick="edit('+p.id+')">Edit</button><button class="del" onclick="del('+p.id+')">Delete</button></div>').join(''):'No products yet';
 });
}
function edit(id){
 fetch('/api/v1/products').then(r=>r.json()).then(d=>{
  let p=d.items.find(x=>x.id===id); if(!p)return;
  eid=id;$('name').value=p.name;$('cat').value=p.category;$('desc').value=p.description;
  $('price').value=p.price_bdt;$('stock').value=p.stock;$('img').value=p.image_url;
  $('title').innerText='Edit Product';$('save').innerText='Update Product';$('cancel').style.display='inline';
 });
}
function cancelEdit(){eid=null;['name','cat','desc','price','stock','img'].forEach(x=>$(x).value='');$('title').innerText='Add Product';$('save').innerText='Add Product';$('cancel').style.display='none'}
function save(){
 let b={name:$('name').value,category:$('cat').value,description:$('desc').value,price_bdt:Number($('price').value),stock:Number($('stock').value),image_url:$('img').value};
 fetch(eid?'/api/v1/products/'+eid:'/api/v1/products',{method:eid?'PUT':'POST',headers:{'Content-Type':'application/json','X-Admin-Key':$('key').value},body:JSON.stringify(b)})
 .then(r=>r.json()).then(d=>{alert(d.message||d.error);if(!d.error){cancelEdit();load()}});
}
function del(id){
 if(!confirm('পণ্যটি মুছে ফেলবেন?'))return;
 fetch('/api/v1/products/'+id,{method:'DELETE',headers:{'X-Admin-Key':$('key').value}})
 .then(r=>r.json()).then(d=>{alert(d.message||d.error);load()});
}
function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
load();
</script></body></html>"""

@app.get("/")
def home(): return jsonify(name="Qayes Online Shop", status="running", currency="BDT")

@app.get("/health")
def health(): return jsonify(status="ok")

@app.get("/admin")
def admin(): return render_template_string(HTML)

@app.get("/api/v1/products")
def products():
    c=db(); rows=c.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall(); c.close()
    return jsonify(items=[dict(r) for r in rows])

@app.post("/api/v1/products")
def add():
    if not auth(): return jsonify(error="Unauthorized"),401
    d=request.get_json(silent=True) or {}
    try:
        name=str(d.get("name","")).strip(); price=int(d.get("price_bdt",0)); stock=int(d.get("stock",0))
        if not name or price<0 or stock<0: raise ValueError
    except: return jsonify(error="নাম, দাম ও স্টক সঠিক দিন"),400
    c=db(); cur=c.execute("INSERT INTO products(name,category,description,price_bdt,stock,image_url) VALUES(?,?,?,?,?,?)",(name,d.get("category",""),d.get("description",""),price,stock,d.get("image_url",""))); c.commit(); pid=cur.lastrowid; c.close()
    return jsonify(message="Product added",id=pid)

@app.put("/api/v1/products/<int:pid>")
def update(pid):
    if not auth(): return jsonify(error="Unauthorized"),401
    d=request.get_json(silent=True) or {}
    try:
        name=str(d.get("name","")).strip(); price=int(d.get("price_bdt",0)); stock=int(d.get("stock",0))
        if not name or price<0 or stock<0: raise ValueError
    except: return jsonify(error="নাম, দাম ও স্টক সঠিক দিন"),400
    c=db(); cur=c.execute("UPDATE products SET name=?,category=?,description=?,price_bdt=?,stock=?,image_url=? WHERE id=?",(name,d.get("category",""),d.get("description",""),price,stock,d.get("image_url",""),pid)); c.commit(); n=cur.rowcount; c.close()
    return (jsonify(message="Product updated"),200) if n else (jsonify(error="Product not found"),404)

@app.delete("/api/v1/products/<int:pid>")
def delete(pid):
    if not auth(): return jsonify(error="Unauthorized"),401
    c=db(); cur=c.execute("DELETE FROM products WHERE id=?",(pid,)); c.commit(); n=cur.rowcount; c.close()
    return (jsonify(message="Product deleted"),200) if n else (jsonify(error="Product not found"),404)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
