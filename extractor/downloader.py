"""
YouTube video downloader module.
Uses yt-dlp to fetch video info and download videos.
"""

import os

import yt_dlp

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
)

console = Console()


def get_video_info(url: str) -> dict | None:
    """
    Fetch video information (title, duration) without downloading.

    Args:
        url: YouTube URL

    Returns:
        dict with 'title', 'duration', 'url' or None if failed
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "url": url,
                "id": info.get("id", ""),
            }
    except Exception as e:
        console.print(f"  [red]✗ Failed to fetch info from:[/red] {url}")
        console.print(f"    [dim]{e}[/dim]")
        return None


def get_all_videos_info(video_dict: dict) -> dict:
    """
    Fetch info for all videos organized by category.

    Args:
        video_dict: dict of {category: [url_list]}

    Returns:
        dict of {category: [video_info_list]}
    """
    result = {}
    total_urls = sum(len(urls) for urls in video_dict.values())
    processed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("🔍 Fetching video info...", total=total_urls)

        for category, urls in video_dict.items():
            category_videos = []
            for url in urls:
                info = get_video_info(url)
                if info:
                    category_videos.append(info)
                processed += 1
                progress.update(
                    task,
                    completed=processed,
                    description=f"🔍 [{category}] ({processed}/{total_urls})",
                )

            if category_videos:
                result[category] = category_videos

    return result


def download_video(url: str, output_dir: str, filename: str | None = None) -> str | None:
    """
    Download a YouTube video as an mp4 file.

    Args:
        url: YouTube URL
        output_dir: directory to save the file
        filename: filename (without extension); uses video ID if not specified

    Returns:
        path of the downloaded file, or None if failed
    """
    os.makedirs(output_dir, exist_ok=True)

    if filename:
        output_template = os.path.join(output_dir, f"{filename}.%(ext)s")
    else:
        output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "progress_hooks": [],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if filename:
                video_path = os.path.join(output_dir, f"{filename}.mp4")
            else:
                video_id = info.get("id", "video")
                video_path = os.path.join(output_dir, f"{video_id}.mp4")

            if os.path.exists(video_path):
                return video_path

            # If .mp4 not found, look for other video files
            for f in os.listdir(output_dir):
                if f.endswith((".mp4", ".mkv", ".webm")):
                    return os.path.join(output_dir, f)

            return None

    except Exception as e:
        console.print(f"  [red]✗ Download failed:[/red] {e}")
        return None
