"""
Frame extraction module.
Uses OpenCV to extract frames from video files at specified intervals.
"""

import os

import cv2

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


def calculate_frame_count(duration: int, interval: int) -> int:
    """
    Calculate the number of frames that will be extracted from a video.

    Args:
        duration: video duration in seconds
        interval: interval between frames in seconds

    Returns:
        Estimated number of frames
    """
    if duration <= 0 or interval <= 0:
        return 0
    return (duration // interval) + 1


def extract_frames(
    video_path: str,
    output_dir: str,
    interval_sec: int,
    image_format: str = "jpg",
    quality: int = 95,
    show_progress: bool = True,
) -> int:
    """
    Extract frames from a video at every N seconds.

    Args:
        video_path: path to the video file
        output_dir: directory to save extracted frames
        interval_sec: interval between frames in seconds
        image_format: image file format ('jpg' or 'png')
        quality: JPEG quality (1-100)
        show_progress: whether to show a progress bar

    Returns:
        Number of frames actually saved
    """
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        console.print(f"  [red]✗ Failed to open video file:[/red] {video_path}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    # Calculate expected frame count
    expected_frames = calculate_frame_count(int(duration), interval_sec)

    # Frame interval (number of frames to skip)
    frame_interval = int(fps * interval_sec)
    if frame_interval <= 0:
        frame_interval = 1

    # Set up encoding parameters
    if image_format.lower() == "png":
        encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        ext = ".png"
    else:
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        ext = ".jpg"

    frame_count = 0
    saved_count = 0

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=25),
            TextColumn("{task.completed}/{task.total} frames"),
            console=console,
        ) as progress:
            task = progress.add_task("    Extracting", total=expected_frames)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_interval == 0:
                    frame_filename = f"frame_{saved_count + 1:04d}{ext}"
                    frame_path = os.path.join(output_dir, frame_filename)
                    cv2.imwrite(frame_path, frame, encode_params)
                    saved_count += 1
                    progress.update(task, completed=saved_count)

                frame_count += 1

            progress.update(task, completed=saved_count, total=saved_count)
    else:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                frame_filename = f"frame_{saved_count + 1:04d}{ext}"
                frame_path = os.path.join(output_dir, frame_filename)
                cv2.imwrite(frame_path, frame, encode_params)
                saved_count += 1

            frame_count += 1

    cap.release()
    return saved_count
