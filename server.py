import uvicorn
from fastmcp import FastMCP

from fastmcp.server.auth.providers.jwt import JWTVerifier

from starlette.applications import Starlette
from starlette.routing import Mount

import os

from mcp_server import mcp_server
from documents_server import documents_server


# Create an MCP server
main = FastMCP("Hopper KB", 
           auth = JWTVerifier(
                jwks_uri=os.environ.get("JWKS_ENDPOINT", ""),
                issuer=os.environ.get("ISSUER_URL", "http://localhost:8000"),
                algorithm=os.environ.get("JWT_ALGORITHM", "RS256")
            )
    )

mcp_app = mcp_server.http_app(path='/', transport="streamable-http", json_response=True)
docs_app = documents_server.http_app(path='/', transport="streamable-http", json_response=True)

app = Starlette(
    routes=[
        Mount("/mcp", app=mcp_app),
        Mount("/docs", app=docs_app)
    ],
    lifespan=mcp_app.lifespan,
)

if __name__ == "__main__":
   uvicorn.run(app=app, host="0.0.0.0", port=int(os.environ.get("MCP_PORT", 8000)), log_level="debug")