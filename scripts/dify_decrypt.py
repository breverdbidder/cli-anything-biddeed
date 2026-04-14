#!/usr/bin/env python3
"""Decrypt a Dify HYBRID-encrypted credential blob.
Run inside docker-api-1 container.
Reads /tmp/blob.json, writes /tmp/plain.txt.
"""
import json, sys, os
sys.path.insert(0, '/app/api')

with open('/tmp/blob.json') as f:
    enc = json.load(f)

key_blob = enc.get('google_api_key') or enc.get('api_key') or list(enc.values())[0]
tenant_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('DIFY_TENANT_ID', '')
if not tenant_id:
    print('ERROR: tenant_id required as arg1 or DIFY_TENANT_ID env', file=sys.stderr)
    sys.exit(2)

# Method 1: direct rsa.decrypt (no flask context)
try:
    from libs import rsa
    plain = rsa.decrypt(key_blob, tenant_id)
    if isinstance(plain, bytes):
        plain = plain.decode()
    with open('/tmp/plain.txt', 'w') as f:
        f.write(plain)
    print(f'OK_method=rsa.decrypt len={len(plain)} starts={plain[:6]}')
    sys.exit(0)
except Exception as e:
    print(f'rsa.decrypt failed: {type(e).__name__}: {e}', file=sys.stderr)

# Method 2: encrypter.decrypt_token (with flask app context)
try:
    from app_factory import create_app
    app = create_app()
    with app.app_context():
        from core.helper.encrypter import decrypt_token
        plain = decrypt_token(tenant_id, key_blob)
        if isinstance(plain, bytes):
            plain = plain.decode()
        with open('/tmp/plain.txt', 'w') as f:
            f.write(plain)
        print(f'OK_method=encrypter len={len(plain)} starts={plain[:6]}')
        sys.exit(0)
except Exception as e:
    print(f'encrypter.decrypt_token failed: {type(e).__name__}: {e}', file=sys.stderr)

sys.exit(1)
