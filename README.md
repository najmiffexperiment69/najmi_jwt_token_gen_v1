<div align="center">

# ⚡ JWT-OB54 API

### 🚀 Fast • Async • Protobuf • JWT • Free Fire Authentication API

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Ge​vent-Async-00A98F?style=for-the-badge" alt="Gevent">
  <img src="https://img.shields.io/badge/Protobuf-Enabled-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Protobuf">
</p>

<a href="https://github.com/Itz-Jahid-X/JWT-OB54">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=22&duration=2800&pause=900&color=00E5FF&center=true&vCenter=true&width=700&lines=JWT-OB54+%7C+High-Speed+API;Access+Token+%E2%86%92+OpenID+%E2%86%92+JWT;Flask+%2B+Gevent+%2B+Protobuf;Built+for+fast+API+workflows" alt="Typing animation">
</a>

<br>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:111827,50:2563EB,100:06B6D4&height=140&section=header&text=JWT-OB54&fontSize=48&fontColor=ffffff&animation=twinkling&fontAlignY=38" width="100%" alt="Animated header">

</div>

---

## ✨ Overview

**JWT-OB54** is a Flask-based API project designed around a fast authentication/token workflow.

The application provides two main HTTP endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /access-jwt` | Accepts an access token, resolves `open_id` when needed, then attempts to generate a JWT through the MajorLogin flow |
| `GET /token` | Accepts guest credentials, requests an OAuth access token, then continues into the JWT generation flow |

The implementation uses **Gevent concurrency**, **AES-CBC encryption**, **Protocol Buffers**, **PyJWT**, and HTTP connection pooling.

> ⚠️ **Important:** This project interacts with third-party game/authentication services. Use it only with accounts and credentials you are authorized to use, and follow the applicable service terms.

---

## 🧠 How It Works

```mermaid
flowchart TD
    A[Client Request] --> B{Endpoint}
    B -->|/access-jwt| C[Read access_token]
    B -->|/token| D[Guest OAuth Request]
    D --> E[Receive access_token + open_id]
    C --> F{open_id supplied?}
    F -->|No| G[Inspect Access Token]
    F -->|Yes| H[Use supplied open_id]
    G --> H
    E --> H
    H --> I[Build GameData protobuf]
    I --> J[AES-CBC Encryption]
    J --> K[Parallel MajorLogin Attempts]
    K --> L[Parse protobuf / JSON response]
    L --> M[Decode JWT payload]
    M --> N[Return JSON]
```

---

## ⚡ Key Features

### 🚀 Concurrent platform attempts
Multiple platform values are attempted concurrently using **Gevent**, allowing the first successful response to be used.

### 🔐 AES encrypted payload
The serialized game data is encrypted using **AES-CBC** before being sent to the MajorLogin endpoint.

### 📦 Protocol Buffers
Game data is serialized through the generated protobuf modules:

```text
my_pb2.py
output_pb2.py
```

### 🌐 Connection pooling
A shared `requests.Session()` uses an HTTP adapter with connection pooling to reduce repeated connection overhead.

### 🧾 JWT parsing
The returned JWT is decoded to extract useful fields such as:

```text
account_id
nickname
external_type
lock_region
token
```

### 🪶 Lightweight JSON responses
`orjson` is used when available, with a standard-library JSON fallback.

---

## 📁 Project Structure

```text
JWT-OB54/
│
├── app.py              # Main Flask application
├── my_pb2.py           # Generated protobuf definitions
├── output_pb2.py       # Generated response protobuf definitions
├── requirements.txt    # Python dependencies
├── vercel.json         # Deployment configuration
├── README.md           # Project documentation
└── .gitignore          # Recommended: keep secrets/cache out of Git
```

---

## 🛠️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/Itz-Jahid-X/JWT-OB54.git
cd JWT-OB54
```

### 2. Create a virtual environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the API

```bash
python app.py
```

The local server starts on:

```text
http://127.0.0.1:1080
```

---

## 🔥 API Usage

### 🌐 Base URL

After deploying the project, replace `YOUR_DOMAIN` with your API domain:

```text
https://YOUR_DOMAIN
```

---

### 🔑 1. Access Token → JWT

This is the main **Access Token → JWT** API.

#### API Format

```http
GET /access-jwt?access_token=YOUR_ACCESS_TOKEN
```

#### Full URL

```text
https://YOUR_DOMAIN/access-jwt?access_token=YOUR_ACCESS_TOKEN
```

#### With `open_id`

```http
GET /access-jwt?access_token=YOUR_ACCESS_TOKEN&open_id=YOUR_OPEN_ID
```

#### Full URL

```text
https://YOUR_DOMAIN/access-jwt?access_token=YOUR_ACCESS_TOKEN&open_id=YOUR_OPEN_ID
```

#### Parameters

| Parameter | Required | Description |
|---|---|---|
| `access_token` | ✅ Yes | Valid access token |
| `open_id` | ❌ No | OpenID; can be supplied directly |

#### Example

```bash
curl "https://YOUR_DOMAIN/access-jwt?access_token=YOUR_ACCESS_TOKEN"
```

#### Success Response

```json
{
  "status": "success",
  "account_id": "ACCOUNT_ID",
  "account_name": "PLAYER_NAME",
  "open_id": "OPEN_ID",
  "access_token": "ACCESS_TOKEN",
  "platform": "PLATFORM",
  "region": "REGION",
  "token": "JWT_TOKEN"
}
```

> 💡 **Flow:** `ACCESS_TOKEN → OPEN_ID → MAJORLOGIN → JWT`

---

### 👤 2. UID + Password → JWT

The `/token` endpoint starts from guest credentials and continues through the OAuth → JWT workflow.

#### API Format

```http
GET /token?uid=YOUR_UID&password=YOUR_PASSWORD
```

#### Full URL

```text
https://YOUR_DOMAIN/token?uid=YOUR_UID&password=YOUR_PASSWORD
```

#### Parameters

| Parameter | Required | Description |
|---|---|---|
| `uid` | ✅ Yes | Authorized account UID |
| `password` | ✅ Yes | Authorized account credential |

#### Example

```bash
curl "https://YOUR_DOMAIN/token?uid=YOUR_UID&password=YOUR_PASSWORD"
```

> 🔒 **Security:** Never put real passwords, access tokens, cookies, client secrets, or JWTs into public README files, screenshots, Git commits, or issue reports.

---

### ⚡ Quick API Reference

```text
ACCESS TOKEN → JWT
GET https://YOUR_DOMAIN/access-jwt?access_token=YOUR_ACCESS_TOKEN

ACCESS TOKEN + OPEN ID → JWT
GET https://YOUR_DOMAIN/access-jwt?access_token=YOUR_ACCESS_TOKEN&open_id=YOUR_OPEN_ID

UID + PASSWORD → OAuth → JWT
GET https://YOUR_DOMAIN/token?uid=YOUR_UID&password=YOUR_PASSWORD
```

---

## ⚙️ Production

For a Gunicorn + Gevent deployment, the project includes a recommended command:

```bash
gunicorn -k gevent -w 4 --worker-connections 1000 --max-requests 10000 --max-requests-jitter 1000 app:app
```

Tune worker and connection settings according to your server resources and traffic.

---

## 📦 Dependencies

```text
Flask
requests
gevent
pycryptodome
PyJWT
protobuf
orjson
gunicorn
```

Install everything with:

```bash
pip install -r requirements.txt
```

---

## 🛡️ Security Checklist

Before pushing or deploying this project publicly:

- [ ] Remove hardcoded cookies/session values
- [ ] Move secrets to environment variables
- [ ] Rotate any credential that has already been exposed
- [ ] Never log access tokens or passwords
- [ ] Add rate limiting
- [ ] Add authentication for private deployments
- [ ] Use HTTPS in production
- [ ] Keep generated protobuf files version-controlled
- [ ] Add `.env` and cache folders to `.gitignore`

### Recommended `.gitignore`

```gitignore
__pycache__/
*.pyc
.env
venv/
.venv/
*.log
```

---

## 🎨 Animated Tech Stack

<div align="center">

<img src="https://skillicons.dev/icons?i=python,flask,git,github&theme=dark" alt="Tech stack">

<br><br>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&height=3&section=footer" width="80%" alt="divider">

</div>

---

## 📊 Architecture Highlights

```text
                   ┌───────────────────┐
                   │      Client       │
                   └─────────┬─────────┘
                             │
                     HTTP GET Request
                             │
              ┌──────────────┴──────────────┐
              │                             │
        /access-jwt                      /token
              │                             │
              ▼                             ▼
       Access Token                  OAuth Guest Flow
              │                             │
              └──────────────┬──────────────┘
                             ▼
                        open_id
                             │
                             ▼
                    GameData / Protobuf
                             │
                             ▼
                       AES Encryption
                             │
                             ▼
                  Parallel MajorLogin Calls
                             │
                             ▼
                    JWT / Response Parse
                             │
                             ▼
                       JSON Response
```

---

## ⚠️ Disclaimer

This repository is provided for **educational and authorized development purposes**.

The author is not responsible for misuse, account issues, service interruptions, rate-limit violations, or consequences resulting from unauthorized access or automation.

Use the project responsibly and comply with the terms and policies of any third-party service you interact with.

---

<div align="center">

### ⭐ If this project helped you, consider starring the repository!

<a href="https://github.com/Itz-Jahid-X/JWT-OB54">
  <img src="https://img.shields.io/github/stars/Itz-Jahid-X/JWT-OB54?style=for-the-badge&logo=github" alt="GitHub stars">
</a>
<a href="https://github.com/Itz-Jahid-X/JWT-OB54/forks">
  <img src="https://img.shields.io/github/forks/Itz-Jahid-X/JWT-OB54?style=for-the-badge&logo=github" alt="GitHub forks">
</a>

<br><br>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:06B6D4,50:2563EB,100:111827&height=120&section=footer&animation=twinkling" width="100%" alt="Animated footer">

</div>
