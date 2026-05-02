"""
YouTube to Dataset Extractor — CLI Entry Point
Extract image datasets from YouTube videos via Terminal
"""

import json
import os
import shutil
import sys
import zipfile
from datetime import datetime

from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.text import Text

from extractor.downloader import get_video_info, get_all_videos_info, download_video
from extractor.frame_extractor import extract_frames, calculate_frame_count
from extractor.utils import (
    print_banner,
    print_summary_table,
    print_single_video_table,
    format_duration,
    sanitize_filename,
    validate_youtube_url,
)

console = Console()

# ──────────────────────────────────────────────
# Directories
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")


def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# Step 1: Choose Input Mode
# ──────────────────────────────────────────────
def choose_input_mode() -> str:
    """Let the user choose the input method."""
    console.print("[bold cyan]📥 Choose video input method:[/bold cyan]")
    console.print("  [white][1][/white] Enter a YouTube URL directly")
    console.print("  [white][2][/white] Use a JSON file (place it in the [cyan]input/[/cyan] folder)")
    console.print()

    choice = Prompt.ask("👉 Select", choices=["1", "2"], default="1")
    return choice


def get_urls_from_input() -> tuple[dict, str]:
    """
    Get a URL from direct user input.

    Returns:
        tuple of (video_dict, mode)
        mode = "single" for a single URL
    """
    console.print()
    url = Prompt.ask("🔗 Enter YouTube URL")

    if not validate_youtube_url(url.strip()):
        console.print("[red]✗ Invalid URL. Please enter a valid YouTube URL.[/red]")
        sys.exit(1)

    return {"direct_input": [url.strip()]}, "single"


def get_urls_from_json() -> tuple[dict, str]:
    """
    Read URLs from a JSON file.

    Returns:
        tuple of (video_dict, mode)
        mode = "multi" for JSON batch
    """
    # Find JSON files in input/ and root directories
    json_files = []

    # Search in input/
    if os.path.exists(INPUT_DIR):
        for f in sorted(os.listdir(INPUT_DIR)):
            if f.endswith(".json"):
                json_files.append(os.path.join(INPUT_DIR, f))

    # Search in root directory
    for f in sorted(os.listdir(BASE_DIR)):
        if f.endswith(".json"):
            full_path = os.path.join(BASE_DIR, f)
            if full_path not in json_files:
                json_files.append(full_path)

    if not json_files:
        console.print(
            "[red]✗ No JSON files found in input/ or root directory.[/red]"
        )
        console.print(
            "[dim]  Please place a JSON file in the input/ folder and try again.[/dim]"
        )
        sys.exit(1)

    console.print()
    console.print("[bold cyan]📂 JSON files found:[/bold cyan]")
    for i, f in enumerate(json_files, 1):
        rel_path = os.path.relpath(f, BASE_DIR)
        console.print(f"  [white][{i}][/white] {rel_path}")

    console.print()
    choice = IntPrompt.ask(
        "👉 Select file",
        default=1,
    )

    if choice < 1 or choice > len(json_files):
        console.print("[red]✗ Invalid selection.[/red]")
        sys.exit(1)

    json_path = json_files[choice - 1]

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ Invalid JSON file: {e}[/red]")
        sys.exit(1)

    # Validate JSON format
    if not isinstance(data, dict):
        console.print("[red]✗ Invalid JSON format. Must be an object with category names as keys.[/red]")
        sys.exit(1)

    total_urls = sum(len(urls) for urls in data.values())
    console.print(
        f"\n[green]✓[/green] File loaded successfully: "
        f"[cyan]{len(data)}[/cyan] categories, "
        f"[cyan]{total_urls}[/cyan] URLs"
    )

    return data, "multi"


# ──────────────────────────────────────────────
# Step 2: Choose Interval
# ──────────────────────────────────────────────
def choose_interval() -> int:
    """Let the user choose the frame capture interval."""
    console.print()
    console.print("[bold cyan]⏱️  How often should frames be captured?[/bold cyan]")
    console.print("[dim]  Examples: 1 = every 1 second, 30 = every 30 seconds, 60 = every 1 minute[/dim]")
    console.print()

    interval = IntPrompt.ask("👉 Enter interval in seconds", default=30)

    if interval <= 0:
        console.print("[red]✗ Interval must be greater than 0.[/red]")
        sys.exit(1)

    return interval


# ──────────────────────────────────────────────
# Step 3-5: Processing
# ──────────────────────────────────────────────
def process_single_url(url_dict: dict, interval: int) -> None:
    """Process a single URL."""
    url = url_dict["direct_input"][0]

    # Fetch video info
    console.print()
    with console.status("🔍 Fetching video information..."):
        info = get_video_info(url)

    if not info:
        console.print("[red]✗ Failed to fetch video information.[/red]")
        sys.exit(1)

    console.print(f"[green]✓[/green] [bold]{info['title']}[/bold]")
    console.print(f"  ⏱️  Duration: {format_duration(info['duration'])}")
    console.print()

    # Show summary table
    total_frames = print_single_video_table(info, interval)

    if total_frames == 0:
        console.print("[red]✗ No frames to extract (video too short or interval too large).[/red]")
        sys.exit(1)

    # Confirm
    console.print()
    if not Confirm.ask("✅ Proceed with dataset creation?", default=True):
        console.print("[yellow]Operation cancelled.[/yellow]")
        sys.exit(0)

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_dir = os.path.join(OUTPUT_DIR, f"dataset_{timestamp}")
    video_folder = sanitize_filename(info["title"])
    frames_dir = os.path.join(dataset_dir, video_folder)

    # Download video
    console.print()
    console.print("[bold cyan]🔄 Downloading video...[/bold cyan]")
    video_path = download_video(url, TEMP_DIR, sanitize_filename(info["id"]))

    if not video_path:
        console.print("[red]✗ Video download failed.[/red]")
        sys.exit(1)

    console.print(f"[green]✓[/green] Download complete")

    # Extract frames
    console.print()
    console.print("[bold cyan]🖼️  Extracting frames...[/bold cyan]")
    saved = extract_frames(video_path, frames_dir, interval)
    console.print(f"[green]✓[/green] Extracted [bold]{saved}[/bold] frames")

    # Save summary.json
    save_summary(dataset_dir, {"direct_input": [info]}, interval, saved)

    # Create ZIP
    console.print()
    zip_path = create_zip(dataset_dir)

    # Clean up temp files
    cleanup_temp()

    # Show results
    print_result(dataset_dir, zip_path, saved)


def process_json_urls(video_dict: dict, interval: int) -> None:
    """Process multiple URLs from a JSON file."""
    # Fetch all video info
    console.print()
    categories_info = get_all_videos_info(video_dict)

    if not categories_info:
        console.print("[red]✗ Failed to fetch any video information.[/red]")
        sys.exit(1)

    # Show summary table
    console.print()
    total_frames = print_summary_table(categories_info, interval)

    if total_frames == 0:
        console.print("[red]✗ No frames to extract.[/red]")
        sys.exit(1)

    # Confirm
    console.print()
    if not Confirm.ask("✅ Proceed with dataset creation?", default=True):
        console.print("[yellow]Operation cancelled.[/yellow]")
        sys.exit(0)

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_dir = os.path.join(OUTPUT_DIR, f"dataset_{timestamp}")

    total_saved = 0
    total_categories = len(categories_info)

    for cat_idx, (category, videos) in enumerate(categories_info.items(), 1):
        console.print()
        console.print(
            f"[bold cyan]🔄 Processing {category} ({cat_idx}/{total_categories})[/bold cyan]"
        )

        for vid_idx, video in enumerate(videos, 1):
            title = video.get("title", "Unknown")
            url = video.get("url", "")

            # Truncate long titles
            display_title = title if len(title) <= 50 else title[:47] + "..."
            console.print(
                f"  [white]↳ [{vid_idx}/{len(videos)}][/white] {display_title}"
            )

            # Download
            console.print(f"    [dim]Downloading...[/dim]")
            video_path = download_video(
                url, TEMP_DIR, sanitize_filename(video.get("id", f"video_{vid_idx}"))
            )

            if not video_path:
                console.print(f"    [red]✗ Skipping this video.[/red]")
                continue

            # Create frames directory
            video_folder = sanitize_filename(title)
            frames_dir = os.path.join(dataset_dir, category, video_folder)

            # Extract frames
            saved = extract_frames(video_path, frames_dir, interval)
            total_saved += saved
            console.print(f"    [green]✓ {saved} frames[/green]")

            # Remove temp video to save disk space
            try:
                os.remove(video_path)
            except OSError:
                pass

    # Save summary.json
    save_summary(dataset_dir, categories_info, interval, total_saved)

    # Create ZIP
    console.print()
    zip_path = create_zip(dataset_dir)

    # Clean up temp files
    cleanup_temp()

    # Show results
    print_result(dataset_dir, zip_path, total_saved)


# ──────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────
def save_summary(dataset_dir: str, categories: dict, interval: int, total_frames: int) -> None:
    """Save summary.json in the dataset directory."""
    summary = {
        "created_at": datetime.now().isoformat(),
        "interval_seconds": interval,
        "total_frames": total_frames,
        "categories": {},
    }

    for category, videos in categories.items():
        summary["categories"][category] = {
            "video_count": len(videos),
            "videos": [
                {
                    "title": v.get("title", "Unknown"),
                    "url": v.get("url", ""),
                    "duration": v.get("duration", 0),
                }
                for v in videos
            ],
        }

    summary_path = os.path.join(dataset_dir, "summary.json")
    os.makedirs(dataset_dir, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def create_zip(dataset_dir: str) -> str:
    """Create a ZIP file from the dataset directory."""
    zip_path = f"{dataset_dir}.zip"
    console.print("[bold cyan]📦 Creating ZIP file...[/bold cyan]")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(dataset_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(dataset_dir))
                zf.write(file_path, arcname)

    # Show ZIP size
    zip_size = os.path.getsize(zip_path)
    if zip_size > 1_000_000_000:
        size_str = f"{zip_size / 1_000_000_000:.1f} GB"
    elif zip_size > 1_000_000:
        size_str = f"{zip_size / 1_000_000:.1f} MB"
    else:
        size_str = f"{zip_size / 1_000:.1f} KB"

    console.print(f"[green]✓[/green] ZIP created successfully ({size_str})")
    return zip_path


def cleanup_temp() -> None:
    """Remove temporary files."""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)


def print_result(dataset_dir: str, zip_path: str, total_frames: int) -> None:
    """Display final results."""
    rel_dataset = os.path.relpath(dataset_dir, BASE_DIR)
    rel_zip = os.path.relpath(zip_path, BASE_DIR)

    result_text = Text()
    result_text.append("🎉 Dataset created successfully!\n\n", style="bold green")
    result_text.append(f"📁 Folder: ", style="white")
    result_text.append(f"{rel_dataset}/\n", style="cyan")
    result_text.append(f"📦 ZIP: ", style="white")
    result_text.append(f"{rel_zip}\n", style="cyan")
    result_text.append(f"🖼️  Frames: ", style="white")
    result_text.append(f"{total_frames} images", style="yellow bold")

    console.print()
    console.print(
        Panel(
            result_text,
            border_style="green",
            padding=(1, 2),
        )
    )


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main() -> None:
    """Main entry point."""
    try:
        ensure_dirs()
        print_banner()

        # Step 1: Choose input mode
        mode = choose_input_mode()

        if mode == "1":
            video_data, data_mode = get_urls_from_input()
        else:
            video_data, data_mode = get_urls_from_json()

        # Step 2: Choose interval
        interval = choose_interval()

        # Step 3-6: Process
        if data_mode == "single":
            process_single_url(video_data, interval)
        else:
            process_json_urls(video_data, interval)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Cancelled by user.[/yellow]")
        cleanup_temp()
        sys.exit(0)


if __name__ == "__main__":
    main()