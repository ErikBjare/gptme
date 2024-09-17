import logging

from .base import ToolSpec

logger = logging.getLogger(__name__)

try:
    # noreorder
    from youtube_transcript_api import YouTubeTranscriptApi  # fmt: skip
except ImportError:
    YouTubeTranscriptApi = None


def get_transcript(video_id: str) -> str:
    if not YouTubeTranscriptApi:
        return "Error: youtube_transcript_api is not installed."
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry["text"] for entry in transcript])
    except Exception as e:
        logger.error(f"Error fetching transcript: {e}")
        return f"Error fetching transcript: {e}"


def summarize_transcript(transcript: str) -> str:
    # noreorder
    from ..llm import summarize as llm_summarize  # fmt: skip

    return llm_summarize(transcript).content


tool: ToolSpec = ToolSpec(
    name="youtube",
    desc="Fetch and summarize YouTube video transcripts",
    instructions="""
    To use this tool, provide a YouTube video ID and specify whether you want the transcript or a summary.
    """,
    functions=[get_transcript, summarize_transcript],
    block_types=["youtube"],
    available=bool(YouTubeTranscriptApi),
)
