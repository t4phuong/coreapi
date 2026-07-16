import base64
import json
import hmac
import hashlib

def encode_jwt(payload, secret):
    header = {"alg": "HS256", "typ": "JWT"}
    b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = hmac.new(secret.encode(), f"{b64_header}.{b64_payload}".encode(), hashlib.sha256).digest()
    b64_signature = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    return f"{b64_header}.{b64_payload}.{b64_signature}"

print(encode_jwt({"user_id": 1}, "mysecret"))
