import os, sqlite3
from flask import Flask, jsonify, request, render_template_string
app=Flask(__name__)
DB=os.environ.get('DATABASE_PATH','qayes.db'); ADMIN_KEY=os.environ.get('ADMIN_KEY','change-me')
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
 c=conn(); c.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,category TEXT DEFAULT '',description TEXT DEFAULT '',price_bdt REAL DEFAULT 0,stock INTEGER DEFAULT 0,image_url TEXT DEFAULT '',active INTEGER DEFAULT 1)"); c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
 for k,v in {'shop_name':'Qayes Online Shop','delivery_charge_bdt':'60','card_enabled':'1','bkash_enabled':'1','nagad_enabled':'1','cod_enabled':'1'}.items(): c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
 c.commit(); c.close()
def ok(): return request.headers.get('X-Admin-Key','')==ADMIN_KEY
def settings():
 c=conn(); d={r['key']:r['value'] for r in c.execute('SELECT key,value FROM settings')}; c.close(); return {'shop_name':d.get('shop_name','Qayes Online Shop'),'delivery_charge_bdt':float(d.get('delivery_charge_bdt','60')),'card_enabled':d.get('card_enabled','1')=='1','bkash_enabled':d.get('bkash_enabled','1')=='1','nagad_enabled':d.get('nagad_enabled','1')=='1','cod_enabled':d.get('cod_enabled','1')=='1'}
@app.get('/')
def home(): return jsonify(name='Qayes Online Shop',status='running',currency='BDT')
@app.get('/health')
def health(): return jsonify(status='ok')
@app.get('/api/v1/products')
def products():
 c=conn(); rows=c.execute('SELECT * FROM products WHERE active=1 ORDER BY id DESC').fetchall(); c.close(); return jsonify(items=[dict(r) for r in rows],currency='BDT')
@app.get('/api/v1/settings')
def pub_settings(): return jsonify(settings())
@app.get('/api/v1/admin/settings')
def admin_settings(): return (jsonify(settings()) if ok() else (jsonify(error='Unauthorized'),401))
@app.put('/api/v1/admin/settings')
def save_settings():
 if not ok(): return jsonify(error='Unauthorized'),401
 d=request.get_json(silent=True) or {}; c=conn()
 for k in ['shop_name','delivery_charge_bdt','card_enabled','bkash_enabled','nagad_enabled','cod_enabled']:
  if k in d:
   v=d[k]
   if k.endswith('_enabled'): v='1' if bool(v) else '0'
   elif k=='delivery_charge_bdt': v=str(float(v))
   else: v=str(v)
   c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,v))
 c.commit(); c.close(); return jsonify(ok=True,settings=settings())
@app.post('/api/v1/admin/products')
def add_product():
 if not ok(): return jsonify(error='Unauthorized'),401
 d=request.get_json(silent=True) or {}
 if not d.get('name'): return jsonify(error='Product name is required'),400
 c=conn(); cur=c.execute('INSERT INTO products(name,category,description,price_bdt,stock,image_url) VALUES(?,?,?,?,?,?)',(d.get('name',''),d.get('category',''),d.get('description',''),float(d.get('price_bdt',0)),int(d.get('stock',0)),d.get('image_url',''))); c.commit(); pid=cur.lastrowid; c.close(); return jsonify(ok=True,id=pid),201
@app.put('/api/v1/admin/products/<int:pid>')
def edit_product(pid):
 if not ok(): return jsonify(error='Unauthorized'),401
 d=request.get_json(silent=True) or {}; c=conn()
 if not c.execute('SELECT id FROM products WHERE id=?',(pid,)).fetchone(): c.close(); return jsonify(error='Product not found'),404
 c.execute('UPDATE products SET name=?,category=?,description=?,price_bdt=?,stock=?,image_url=?,active=? WHERE id=?',(d.get('name',''),d.get('category',''),d.get('description',''),float(d.get('price_bdt',0)),int(d.get('stock',0)),d.get('image_url',''),1 if d.get('active',True) else 0,pid)); c.commit(); c.close(); return jsonify(ok=True)
@app.delete('/api/v1/admin/products/<int:pid>')
def delete_product(pid):
 if not ok(): return jsonify(error='Unauthorized'),401
 c=conn(); c.execute('UPDATE products SET active=0 WHERE id=?',(pid,)); c.commit(); c.close(); return jsonify(ok=True)
HTML='''<!doctype html><html lang="bn"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Qayes Admin</title><style>body{font-family:Arial;background:#f4f6f8;margin:0;padding:16px}.card{background:#fff;padding:16px;margin:12px 0;border-radius:12px}input,textarea{width:100%;box-sizing:border-box;padding:10px;margin:5px 0}button{padding:9px 13px;border:0;border-radius:6px;background:#111;color:#fff;margin:3px}.del{background:#c62828}.edit{background:#1976d2}</style><h2>Qayes Online Shop - Admin</h2><div class="card"><b>Admin Key</b><input id="key" type="password" placeholder="ADMIN_KEY"><button onclick="load()">Refresh</button></div><div class="card"><h3>Shop Settings</h3><input id="shop" placeholder="Shop Name"><input id="delivery" type="number" placeholder="Delivery Charge (BDT)"><label><input id="card" type="checkbox"> Card</label><label><input id="bkash" type="checkbox"> bKash</label><label><input id="nagad" type="checkbox"> Nagad</label><label><input id="cod" type="checkbox"> Cash on Delivery</label><button onclick="save()">Save Settings</button></div><div class="card"><h3>Add Product</h3><input id="name" placeholder="পণ্যের নাম"><input id="cat" placeholder="ক্যাটাগরি"><textarea id="desc" placeholder="বর্ণনা"></textarea><input id="price" type="number" placeholder="দাম (BDT)"><input id="stock" type="number" placeholder="স্টক"><input id="img" placeholder="ছবির URL (ঐচ্ছিক)"><button onclick="add()">Add Product</button></div><div class="card"><h3>Products</h3><div id="list">No products yet</div></div><script>const H=()=>({'Content-Type':'application/json','X-Admin-Key':key.value});async function load(){if(!key.value)return alert('Admin Key দিন');let r=await fetch('/api/v1/admin/settings',{headers:H()});if(r.ok){let d=await r.json();shop.value=d.shop_name;delivery.value=d.delivery_charge_bdt;card.checked=d.card_enabled;bkash.checked=d.bkash_enabled;nagad.checked=d.nagad_enabled;cod.checked=d.cod_enabled}products()}async function save(){let r=await fetch('/api/v1/admin/settings',{method:'PUT',headers:H(),body:JSON.stringify({shop_name:shop.value,delivery_charge_bdt:+delivery.value,card_enabled:card.checked,bkash_enabled:bkash.checked,nagad_enabled:nagad.checked,cod_enabled:cod.checked})});alert(r.ok?'Settings saved':'Failed')}async function add(){let r=await fetch('/api/v1/admin/products',{method:'POST',headers:H(),body:JSON.stringify({name:name.value,category:cat.value,description:desc.value,price_bdt:+price.value,stock:+stock.value,image_url:img.value})});alert(r.ok?'Product added':'Failed');if(r.ok){name.value=cat.value=desc.value=price.value=stock.value=img.value='';products()}}async function products(){let d=await (await fetch('/api/v1/products')).json();list.innerHTML=d.items.length?d.items.map(p=>`<div><b>${p.name}</b> - ৳${p.price_bdt} - Stock: ${p.stock}<br><button class="edit" onclick='edit(${p.id},${JSON.stringify(p.name)},${p.price_bdt},${p.stock})'>Edit</button><button class="del" onclick='del(${p.id})'>Delete</button><hr></div>`).join(''):'No products yet'}async function edit(id,n,p,s){n=prompt('পণ্যের নাম',n);if(n===null)return;p=prompt('দাম (BDT)',p);if(p===null)return;s=prompt('স্টক',s);if(s===null)return;let r=await fetch('/api/v1/admin/products/'+id,{method:'PUT',headers:H(),body:JSON.stringify({name:n,price_bdt:+p,stock:+s,active:true})});alert(r.ok?'Updated':'Failed');products()}async function del(id){if(!confirm('পণ্যটি মুছে দিতে চান?'))return;let r=await fetch('/api/v1/admin/products/'+id,{method:'DELETE',headers:H()});alert(r.ok?'Deleted':'Failed');products()}</script>'''
@app.get('/admin')
def admin(): return render_template_string(HTML)
init()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
