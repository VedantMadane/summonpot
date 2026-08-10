"""Example summonpot app — summon agents behind endpoints."""

from summonpot import Pot


def search_web(query: str) -> list[dict]:
    """Search the web for information."""
    return [{"query": query, "result": "example result"}]


pot = Pot("example-service", tools=[search_web])


@pot.summon("/research")
def research_topic(query: str, depth: str = "standard") -> str:
    """Research this topic thoroughly and return a comprehensive report."""


@pot.summon("/summarize")
def summarize(text: str) -> str:
    """Summarize the given text into key bullet points."""


@pot.summon("/analyze")
def analyze_sentiment(text: str) -> dict:
    """Analyze the text and return a JSON object with sentiment and topics."""