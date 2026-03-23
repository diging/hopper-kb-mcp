import jwt
from functools import wraps
import os, time

from starlette.responses import JSONResponse

from fastmcp.server.auth.providers.jwt import JWTVerifier
    
auth = JWTVerifier(
        jwks_uri=os.environ.get("JWKS_ENDPOINT", ""),
        issuer=os.environ.get("ISSUER_URL", "http://localhost:8000"),
        algorithm=os.environ.get("JWT_ALGORITHM", "RS256")
    )

def require_api_key(func):
    """"
    Decorator to require an API key for certain routes. 
    This is a check for a specific API key in the Authorization header and 
    makes sure the token is valid.
    """
    
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        
        
        token = request.headers.get("Authorization", "")[7:]  # Remove "Bearer " prefix
        if not token:
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        # Validate the token with the verifier
        auth_info = await auth.verify_token(token) 
        if not auth_info:
            return JSONResponse({"error": "Forbidden"}, status_code=403)

        return await func(request, *args, **kwargs)
    return wrapper