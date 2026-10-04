# Qayes Admin + Payment Settings v3

Render:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Add Environment Variable `ADMIN_KEY` with a strong secret.

Admin page: `/admin`

Payment toggles included: Card, bKash, Nagad, COD.
Currency: BDT only.

Note: Card/bKash/Nagad live payments require approved merchant/gateway credentials. This starter does not store card numbers or CVV.
