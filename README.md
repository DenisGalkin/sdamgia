# SDAMGIA Answers

A small FastAPI app that extracts the short answers from a Russian EGE SDAMGIA test variant.

## Deploy

Point a domain's DNS record at the VPS, then create `.env` from `.env.example` and set `DOMAIN` to that hostname. Start everything with:

```sh
docker compose up -d --build
```

Caddy obtains and renews the HTTPS certificate automatically. With no `.env`, the stack still starts on `localhost` using Caddy's local certificate.

## Development

```sh
python -m venv .venv
.venv\\Scripts\\Activate.ps1       # Windows PowerShell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://127.0.0.1:8000` on the host computer. To open it from another
device on the same network, find the host computer's IPv4 address with
`ipconfig`, then use `http://<host-ip>:8000` (for example,
`http://192.168.1.25:8000`). If Windows Firewall prompts for access, allow
Python on private networks.

## Tests

```sh
pytest
```
