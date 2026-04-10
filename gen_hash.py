import hashlib
import secrets

password = "TempPass123!"
salt = secrets.token_hex(16)
hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
result = f"{salt}${hashed}"
print(result)
