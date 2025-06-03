import hashlib
import hmac


def verify_signature(payload_body, secret_token, signature_header) -> tuple:
    """Verify that the payload was sent from GitHub by validating SHA256.

    Raise and return 403 if not authorized.

    Args:
        payload_body: original request body to verify (request.body())
        secret_token: GitHub app webhook token (WEBHOOK_SECRET)
        signature_header: header received from GitHub (x-hub-signature-256)
    """
    if not signature_header:
        return 'x-hub-signature-256 header is missing!', 403
    hash_object = hmac.new(
        secret_token.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        return 'Request signatures didn\'t match!', 403

    return None, 200
