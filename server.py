from mcp.server.fastmcp import FastMCP
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from functools import wraps

import httpx
from markdownify import markdownify as md

from pydantic import AnyHttpUrl
import os, time

import jwt


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



# Add an addition tool
@mcp.tool()
def search(query: str) -> dict:
    """Find relevant documents"""
    return {
        "results": [
            {
                "title": "Respiratory Virus Activity Levels",
                "url": "https://www.cdc.gov/respiratory-viruses/data/activity-levels.html",
                "snippet": "Respiratory illness activity is monitored using the acute respiratory illness (ARI) metric. ARI captures a broad range of diagnoses from emergency department visits for respiratory illnesses, from the common cold to severe infections like influenza, RSV and COVID-19. It captures illnesses that may not present with fever, offering a more complete picture than the previous influenza-like illness (ILI) metric.",
                "id": "DOC1"
            },
            {
                "title": "Measles Cases and Outbreaks",
                "url": "https://www.cdc.gov/measles/data-research/index.html",
                "snippet": "As of March 12, 2026, 1,362 confirmed* measles cases were reported in the United States in 2026. Among these, 1,353 measles cases were reported by 31 jurisdictions: Alaska, Arizona, California, Colorado, Florida, Georgia, Idaho, Illinois, Kentucky, Maine, Massachusetts, Minnesota, Missouri, Nebraska, New Mexico, New York City, New York State, North Carolina, North Dakota, Ohio, Oklahoma, Oregon, Pennsylvania, South Carolina, South Dakota, Texas, Utah, Vermont, Virginia, Washington, and Wisconsin. A total of 9 measles cases were reported among international visitors to the United States.",
                "id": "DOC2"
            } 
        ]
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
        response = httpx.get(url)
        content = md(response.content)
        return Response()
    except Exception as e:
        print(e)
        return Response(status_code=500)



# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")