from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Hopper KB", json_response=True, port=8002)


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


# Run with streamable HTTP transport
if __name__ == "__main__":
    mcp.run(transport="streamable-http")