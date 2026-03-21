from mcp.server.fastmcp import FastMCP
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

from starlette.requests import Request
from starlette.responses import JSONResponse
from functools import wraps

from pydantic import AnyHttpUrl
import os, time
import httpx

import jwt

import documents, searchdocs

class JwtTokenVerifier(TokenVerifier):
    
    async def verify_token(self, token: str) -> AccessToken | None:
        jwks_url = os.environ.get("JWKS_ENDPOINT", "")
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        data = jwt.decode(
            token, 
            key=signing_key.key, # Simplified
            algorithms=os.environ.get("JWT_ALGORITHM", "RS256").split(",")
        )
        
        return AccessToken(
                    token=token,
                    client_id=data.get("client_id", "unknown"),
                    scopes=data.get("scope", "").split() if data.get("scope") else [],
                    expires_at=data.get("exp"),
                    resource=data.get("aud"),  
                )

def require_api_key(func):
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

# Create an MCP server
mcp = FastMCP("Hopper KB", 
              json_response=True, 
              host="0.0.0.0", 
              port=int(os.environ.get("MCP_PORT", 8000)), 
              token_verifier=JwtTokenVerifier(),
              auth=AuthSettings(
                issuer_url=AnyHttpUrl(os.environ.get("ISSUER_URL", "http://localhost:8000/")),  # Authorization Server URL
                resource_server_url=AnyHttpUrl(os.environ.get("RESOURCE_SERVER_URL", "http://localhost:8002/")),  # This server's URL
                required_scopes=os.environ.get("REQUIRED_SCOPES","openid").split(";"),
                )
            )


@mcp.tool()
def search(query: str) -> dict:
    """Find relevant documents"""
    search_results = searchdocs.search(query)

    for chunk in search_results:
        print(f"Id: {chunk['id']}")
        
    return {
        "results": search_results
    }


@mcp.resource("hopper://documents/{id}")
def get_document(id: str) -> str:
    """Get a document"""
    if id == "DOC1":
        with open('documents/DOC1.html', 'r') as file:
            content = file.read()
    else:
        with open('documents/DOC2.html', 'r') as file:
            content = file.read()
    return content

@mcp.custom_route("/website/add", methods=["POST"])
@require_api_key
async def add_website(request: Request):
    url = request.query_params.get("url")
    try:
        documents.add_website(url)
        return JSONResponse({"message": "Website added successfully."})
    except httpx.HTTPError as e:
        print(e)
        return JSONResponse({"error": "Website could not be accessed."}, status_code=500)
    except Exception as e:
        print(e)
        return JSONResponse({"error": "An error occurred while processing the website."}, status_code=500)

# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")