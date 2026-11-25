import os
import re
import uuid
import gzip
from urllib.parse import urlparse
from datetime import datetime

import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, request, Response
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests
import urllib3
from google.protobuf.internal.decoder import _DecodeVarint, _DecodeVarint32

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- optional: JWT decode ----------
try:
    import jwt as pyjwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

# ---------- fast JSON ----------
try:
    import orjson
    def _jsonify(data, status=200):
        return Response(
            orjson.dumps(data),
            status=status,
            mimetype='application/json'
        )
except ImportError:
    import json
    def _jsonify(data, status=200):
        return Response(
            json.dumps(data, separators=(',', ':'), ensure_ascii=False),
            status=status,
            mimetype='application/json'
        )

app = Flask(__name__)

# ---------- API Configuration ----------
API_CREDIT = "@NAJMI_ADMIN"

# ---------- pooled HTTP session ----------
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=100, pool_maxsize=100,
    max_retries=0, pool_block=False
)
session.mount('https://', adapter)
session.mount('http://', adapter)

# ---------- AES keys ----------
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

# ---------- Auto version ----------
DEFAULT_CLIENT_VERSION = "1.108.1"
DEFAULT_OB = "OB55"
FALLBACK_LOGIN_URLS = [
    "https://loginbp.ggblueshark.com",
    "https://loginbphk.freefiremobile.com",
]


def _clean_login_url(u):
    """Shudhu asol LOGIN server nao. CDN/download URL (dl.ak..., ABHotUpdates) nibe na."""
    if not u or not isinstance(u, str):
        return None
    u = u.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    p = urlparse(u)
    host = (p.hostname or "").lower()
    if not host.startswith("login"):
        return None
    return f"https://{p.netloc}"


def _autoupdate():
    # --- client version ---
    play = (os.environ.get("CLIENT_VERSION") or "").strip() or None
    if not play:
        try:
            url = ("https://play.google.com/store/apps/details"
                   "?id=com.dts.freefireth&hl=ar&gl=DZ")
            headers = {
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36")
            }
            r = requests.get(url, headers=headers, timeout=5)
            found = set(re.findall(r'\b(1\.\d{1,3}\.\d{1,3})\b', r.text))
            cands = [tuple(int(x) for x in v.split('.')) for v in found]
            cands = [c for c in cands if c[1] >= 100]
            if cands:
                play = ".".join(str(x) for x in max(cands))
        except Exception:
            pass
    play = play or DEFAULT_CLIENT_VERSION

    # --- login url + OB ---
    login = _clean_login_url(os.environ.get("LOGIN_URL"))
    ob = (os.environ.get("OB_VERSION") or "").strip() or None

    api_url = (
        "https://version.ggwhitehawk.com/live/ver.php"
        f"?version={play}&lang=ar&device=android&channel=android"
        "&appstore=googleplay&region=ME"
        "&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
        "&device_name=Samsung%20SM-S918B"
        "&device_CPU=ARM64%20FP%20ASIMD%20AES"
        "&device_GPU=Adreno%20(TM)%20740&device_mem=8192"
    )
    try:
        r = requests.get(api_url, verify=False, timeout=5)
        data = r.json()
        login = login or _clean_login_url(data.get("server_url"))
        cand = data.get("latest_release_version")
        if not ob and isinstance(cand, str) and re.fullmatch(r"OB\d+", cand):
            ob = cand
        if not login:
            print(f"[!] server_url paoa jay nai, fallback use hocche. keys={list(data.keys())}")
    except Exception as e:
        print(f"[!] version server error: {e}")

    login = login or FALLBACK_LOGIN_URLS[0]
    ob = ob or DEFAULT_OB
    return login, ob, play


LOGIN_URL, OB_VERSION, CLIENT_VERSION = _autoupdate()
LOGIN_URLS = [LOGIN_URL] + [u for u in FALLBACK_LOGIN_URLS if u != LOGIN_URL]
try:
    OB_NUM = int(OB_VERSION[2:])
except ValueError:
    OB_NUM = 55
print(f"[+] login_urls={LOGIN_URLS}  OB={OB_VERSION}  Client={CLIENT_VERSION}")


# ---------- Protobuf helpers ----------
def encode_varint(value):
    out = []
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def build_payload_from_dict(fields_dict):
    payload = b''
    for key, value in sorted(fields_dict.items()):
        field_num = int(key)
        if isinstance(value, bool):
            tag = (field_num << 3) | 0
            payload += encode_varint(tag)
            payload += encode_varint(1 if value else 0)
        elif isinstance(value, int):
            tag = (field_num << 3) | 0
            payload += encode_varint(tag)
            payload += encode_varint(value)
        elif isinstance(value, str):
            tag = (field_num << 3) | 2
            data = value.encode('utf-8')
            payload += encode_varint(tag)
            payload += encode_varint(len(data))
            payload += data
        elif isinstance(value, bytes):
            tag = (field_num << 3) | 2
            payload += encode_varint(tag)
            payload += encode_varint(len(value))
            payload += value
        elif isinstance(value, dict):
            sub = build_payload_from_dict(value)
            tag = (field_num << 3) | 2
            payload += encode_varint(tag)
            payload += encode_varint(len(sub))
            payload += sub
        else:
            raise TypeError(f"Unsupported type for field {field_num}")
    return payload


def decode_protobuf(data):
    pos = 0
    length = len(data)
    fields = {}
    while pos < length:
        key, pos = _DecodeVarint(data, pos)
        field_number = key >> 3
        wire_type = key & 7
        if wire_type == 0:
            value, pos = _DecodeVarint(data, pos)
        elif wire_type == 2:
            size, pos = _DecodeVarint32(data, pos)
            raw = data[pos:pos + size]
            pos += size
            try:
                value = decode_protobuf(raw)
            except Exception:
                value = raw
        elif wire_type == 5:
            value = int.from_bytes(data[pos:pos + 4], 'little')
            pos += 4
        elif wire_type == 1:
            value = int.from_bytes(data[pos:pos + 8], 'little')
            pos += 8
        else:
            raise ValueError(f"Unsupported wire type {wire_type}")
        if field_number in fields:
            if not isinstance(fields[field_number], list):
                fields[field_number] = [fields[field_number]]
            fields[field_number].append(value)
        else:
            fields[field_number] = value
    return fields


def build_major_login_payload(open_id, access_token):
    fields = {
        3: str(datetime.now())[:-7],
        4: "free fire",
        5: 2,
        7: f"{CLIENT_VERSION}",
        8: "Android OS 11 / API-30 (RQ3A.210805.001)",
        9: "Handheld",
        10: "Verizon",
        11: "WIFI",
        12: 1080,
        13: 2400,
        14: "440",
        15: "ARMv8",
        16: 6144,
        17: "Adreno (TM) 650",
        18: "OpenGL ES 3.2 V@1.50",
        19: f"Google|{uuid.uuid4()}",
        20: "",
        21: "en",
        22: open_id,
        23: "4",
        24: "Handheld",
        25: {6: OB_NUM, 8: 81},
        29: access_token,
        30: 2,
        41: "Verizon",
        42: "WIFI",
        57: "7428b253defc164018c604a1ebbfebdf",
        60: 128512,
        61: 38000,
        62: 110731,
        63: 18000,
        64: 18000,
        65: 26628,
        66: 25000,
        67: 119234,
        73: 3,
        74: "/data/app/~~random/base.apk",
        76: 1,
        77: "hash|base.apk",
        78: 3,
        79: 2,
        81: "64",
        83: "2024010012",
        86: "OpenGLES3",
        87: 16383,
        88: 4,
        89: b"FwQVTgUPX1UaUllDDwcWCRBpWAUOUgsvA1snWlBaO1kFYg==",
        92: 9000,
        93: "android",
        94: "",
        95: 110009,
        97: 1,
        98: 0,
        99: "4",
        100: "4",
    }
    return build_payload_from_dict(fields)


def encrypt_message(plaintext: bytes) -> bytes:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(plaintext, AES.block_size))


def strip_major_login_prefix(body: bytes) -> bytes:
    if len(body) <= 64:
        return body
    try:
        d0 = decode_protobuf(body)
        if 8 in d0:
            return body
    except Exception:
        pass
    try:
        d64 = decode_protobuf(body[64:])
        if 8 in d64:
            return body[64:]
    except Exception:
        pass
    return body[64:]


# ---------- OAuth ----------
OAUTH_HEADERS = {
    "User-Agent": "GarenaMSDK/5.5.0P1(SM-G998B;Android 13;en-US;USA;)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "close"
}
OAUTH_PAYLOAD_TEMPLATE = {
    "response_type": "token",
    "client_type": "2",
    "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
    "client_id": "100067"
}


def oauth_guest(uid: str, password: str):
    payload = OAUTH_PAYLOAD_TEMPLATE.copy()
    payload["uid"] = uid
    payload["password"] = password
    try:
        r = session.post(
            "https://100067.connect.garena.com/oauth/guest/token/grant",
            data=payload, headers=OAUTH_HEADERS, timeout=6
        )
    except requests.RequestException as e:
        return None, f"OAuth request error: {e}"

    if r.status_code != 200:
        return None, f"OAuth HTTP {r.status_code}: {r.text[:200]}"
    try:
        j = r.json()
    except ValueError:
        return None, "OAuth invalid JSON"

    open_id = j.get("open_id")
    access_token = j.get("access_token")
    if not open_id or not access_token:
        return None, f"OAuth missing fields: keys={list(j.keys())}"
    return (open_id, access_token), None


# ---------- MajorLogin ----------
MAJOR_ATTEMPTS = 3
MAJOR_TIMEOUT = 5
_state = {"login_idx": 0, "auth": "none"}


def _major_headers(mode: str, access_token: str) -> dict:
    h = {
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-Ga-Sv": "1789534056",
        "X-Ga": "v1 1",
        "ReleaseVersion": OB_VERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Connection": "close",
    }
    if mode == "bearer":
        h["Authorization"] = f"Bearer {access_token.strip()}"
    return h


def major_login(open_id: str, access_token: str):
    plain = build_major_login_payload(open_id, access_token)
    encrypted = encrypt_message(plain)

    idx = _state["login_idx"]
    mode = _state["auth"]
    r = None
    last_err = "MajorLogin failed"

    for attempt in range(1, MAJOR_ATTEMPTS + 1):
        base = LOGIN_URLS[idx % len(LOGIN_URLS)]
        url = base.rstrip('/') + "/MajorLogin"
        try:
            r = session.post(
                url, data=encrypted,
                headers=_major_headers(mode, access_token),
                verify=False, timeout=MAJOR_TIMEOUT
            )
        except requests.RequestException as e:
            last_err = f"MajorLogin request error [{base}]: {e}"
            idx += 1
            continue

        if r.status_code == 200:
            _state["login_idx"], _state["auth"] = idx, mode
            print(f"[MajorLogin] ok attempt={attempt} server={base} auth={mode}")
            break

        last_err = f"MajorLogin HTTP {r.status_code} [{base}]: {r.content[:200]!r}"
        print(f"[MajorLogin] attempt={attempt} server={base} auth={mode} -> {r.status_code}")

        if r.status_code == 400 and b"Authorization" in r.content:
            mode = "bearer" if mode == "none" else "none"
            continue
        if r.status_code in (403, 404) or r.status_code >= 500:
            idx += 1
            continue
        return None, last_err
    else:
        return None, last_err

    body = strip_major_login_prefix(r.content)
    try:
        decoded = decode_protobuf(body)
    except Exception as e:
        return None, f"Protobuf decode failed: {e}"

    token = decoded.get(8)
    if isinstance(token, bytes):
        token = token.decode('utf-8', errors='replace')
    client_url = decoded.get(10)
    if isinstance(client_url, bytes):
        client_url = client_url.decode('utf-8', errors='replace')
    if client_url and not client_url.startswith(('http://', 'https://')):
        client_url = 'https://' + client_url

    if not token:
        return None, "Missing JWT (field 8)"
    if not client_url:
        return None, "Missing client URL (field 10)"

    return {"jwt": token, "client_url": client_url}, None


# ---------- JWT decode ----------
def decode_jwt(token: str) -> dict:
    if not HAS_JWT or not token:
        return {}
    try:
        return pyjwt.decode(token, options={"verify_signature": False})
    except Exception:
        return {}


# ---------- Build final response ----------
def _build_response(open_id, access_token, jwt_token):
    decoded = decode_jwt(jwt_token)

    platform_raw = decoded.get("external_type")
    try:
        platform = int(platform_raw) if platform_raw is not None else None
    except (TypeError, ValueError):
        platform = platform_raw

    return {
        "account_id": decoded.get("account_id"),
        "account_name": decoded.get("nickname"),
        "open_id": open_id,
        "access_token": access_token,
        "platform": platform,
        "region": decoded.get("lock_region"),
        "status": "success",
        "token": jwt_token,
        "credit": API_CREDIT,
    }


# ---------- High-level login ----------
def full_login(uid: str, password: str):
    creds, err = oauth_guest(uid, password)
    if err:
        return None, err
    open_id, access_token = creds

    ml, err = major_login(open_id, access_token)
    if err:
        return None, err

    return _build_response(open_id, access_token, ml["jwt"]), None


# ---------- Routes ----------
@app.route('/token', methods=['GET'])
@app.route('/login', methods=['GET'])
def route_login():
    uid = request.args.get('uid')
    password = request.args.get('password')
    if not uid or not password:
        return _jsonify({"status": "failed", "message": "Missing uid or password", "credit": API_CREDIT}, 400)

    result, err = full_login(uid, password)
    if err:
        return _jsonify({"status": "failed", "message": err, "credit": API_CREDIT}, 400)
    return _jsonify(result)


@app.route('/access-jwt', methods=['GET'])
def route_access_jwt():
    access_token = request.args.get('access_token')
    open_id = request.args.get('open_id')

    if not access_token:
        return _jsonify({"status": "failed", "message": "Missing access_token", "credit": API_CREDIT}, 400)
    if not open_id:
        return _jsonify({"status": "failed", "message": "Missing open_id", "credit": API_CREDIT}, 400)

    ml, err = major_login(open_id, access_token)
    if err:
        return _jsonify({"status": "failed", "message": err, "credit": API_CREDIT}, 400)

    return _jsonify(_build_response(open_id, access_token, ml["jwt"]))


@app.route('/version', methods=['GET'])
def route_version():
    return _jsonify({
        "login_url": LOGIN_URL,
        "login_urls": LOGIN_URLS,
        "ob_version": OB_VERSION,
        "client_version": CLIENT_VERSION,
        "credit": API_CREDIT,
    })


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def route_health():
    return _jsonify({
        "status": "ok",
        "login_url": LOGIN_URL,
        "login_urls": LOGIN_URLS,
        "ob_version": OB_VERSION,
        "client_version": CLIENT_VERSION,
        "jwt_decode": HAS_JWT,
        "credit": API_CREDIT,
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1080, debug=False)
