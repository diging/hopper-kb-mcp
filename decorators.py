import jwt
from functools import wraps
import os, time

from mcp.server.auth.provider import AccessToken, TokenVerifier

from starlette.responses import JSONResponse

class JwtTokenVerifier(TokenVerifier):
    """
    This class implements the TokenVerifier interface for JWT tokens. 
    It retrieves the JWKS from Hopper, verifies the token's signature, and 
    decodes the token so we can check its validity. 
    """
    async def verify_token(self, token: str) -> AccessToken | None:
        jwks_url = os.environ.get("JWKS_ENDPOINT", "")
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        try:
            data = jwt.decode(
                token, 
                key=signing_key.key, # Simplified
                algorithms=os.environ.get("JWT_ALGORITHM", "RS256").split(",")
            )
        except jwt.PyJWTError as e:
            print(f"Token verification failed: {e}")
            return None
        
        return AccessToken(
                    token=token,
                    client_id=data.get("client_id", "unknown"),
                    scopes=data.get("scope", "").split() if data.get("scope") else [],
                    expires_at=data.get("exp"),
                    resource=data.get("aud"),  
                )

def require_api_key(func):
    """"
    Decorator to require an API key for certain routes. 
    This is a check for a specific API key in the Authorization header and 
    makes sure the token is valid.
    """
    
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        verifier = JwtTokenVerifier()

        token = request.headers.get("Authorization", "")[7:]  # Remove "Bearer " prefix
        if not token:
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        # Validate the token with the verifier
        auth_info = await verifier.verify_token(token)
        if not auth_info:
            return JSONResponse({"error": "Forbidden"}, status_code=403)

        if auth_info.expires_at and auth_info.expires_at < int(time.time()):
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        return await func(request, *args, **kwargs)
    return wrapper