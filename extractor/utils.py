"""
Utility functions for the YouTube to Dataset extractor.
"""

import re
import unicodedata

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ──────────────────────────────────────────────
# Credits
# ──────────────────────────────────────────────
GITHUB_USERNAME = "TK17250"
GITHUB_URL = "https://github.com/TK17250"


def print_banner() -> None:
    """Display the welcome banner in the terminal."""
    banner_text = Text()
    banner_text.append("🎬 YouTube to Dataset Extractor\n", style="bold cyan")
    banner_text.append(
        "Extract frames from YouTube videos to build image datasets\n\n",
        style="dim white",
    )
    banner_text.append(f"👤 GitHub: ", style="dim")
    banner_text.append(f"{GITHUB_USERNAME}", style="bold white")
    banner_text.append(f" ({GITHUB_URL})", style="dim cyan")
    console.print(
        Panel(
            banner_text,
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def format_duration(seconds: int) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    if seconds <= 0:
        return "00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def validate_youtube_url(url: str) -> bool:
    """Check if the URL is a valid YouTube link."""
    youtube_patterns = [
        r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^https?://youtu\.be/[\w-]+",
        r"^https?://(www\.)?youtube\.com/shorts/[\w-]+",
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


def sanitize_filename(name: str) -> str:
    """Make a filename safe for all operating systems."""
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name)
    # Remove unsafe characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    # Replace whitespace with underscores
    name = re.sub(r"\s+", "_", name)
    # Truncate to a reasonable length
    name = name[:80]
    # Remove trailing underscores and dots
    name = name.rstrip("_.")
    return name or "untitled"


def print_summary_table(
    categories: dict, interval: int, show_total: bool = True
) -> int:
    """
    Display a summary table of video info and estimated frame counts.

    Args:
        categories: dict of {category_name: [video_info_list]}
        interval: seconds between each frame capture
        show_total: whether to show a Total row

    Returns:
        Total estimated frame count
    """
    from .frame_extractor import calculate_frame_count

    table = Table(
        title="📊 Dataset Summary",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Category", style="bold white", min_width=15)
    table.add_column("Videos", justify="center", style="yellow")
    table.add_column("Total Duration", justify="center", style="green")
    table.add_column("Est. Frames", justify="center", style="magenta")

    total_videos = 0
    total_duration = 0
    total_frames = 0

    for category, videos in categories.items():
        num_videos = len(videos)
        cat_duration = sum(v.get("duration", 0) for v in videos)
        cat_frames = sum(
            calculate_frame_count(v.get("duration", 0), interval) for v in videos
        )

        total_videos += num_videos
        total_duration += cat_duration
        total_frames += cat_frames

        table.add_row(
            category,
            str(num_videos),
            format_duration(cat_duration),
            f"~{cat_frames}",
        )

    if show_total and len(categories) > 1:
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{total_videos}[/bold]",
            f"[bold]{format_duration(total_duration)}[/bold]",
            f"[bold]~{total_frames}[/bold]",
            style="on grey11",
        )

    console.print(table)
    return total_frames


def print_single_video_table(video_info: dict, interval: int) -> int:
    """
    Display a summary table for a single video URL.

    Returns:
        Estimated frame count
    """
    from .frame_extractor import calculate_frame_count

    duration = video_info.get("duration", 0)
    frames = calculate_frame_count(duration, interval)

    table = Table(
        title="📊 Dataset Summary",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Title", style="bold white", min_width=20)
    table.add_column("Duration", justify="center", style="green")
    table.add_column("Interval", justify="center", style="yellow")
    table.add_column("Est. Frames", justify="center", style="magenta")

    title = video_info.get("title", "Unknown")
    # Truncate long titles
    if len(title) > 40:
        title = title[:37] + "..."

    table.add_row(
        title,
        format_duration(duration),
        f"every {interval}s",
        f"~{frames}",
    )

    console.print(table)
    return frames
