import subprocess
import os
import re
import uuid
import shutil
from services.ai_service import generate_srt_gemini, generate_summary_gemini, generate_video_veo

def remove_silence(input_path, output_path, threshold="-30dB", min_silence_len=0.5):
    command_detect = [
        "ffmpeg", "-i", input_path,
        "-af", f"silencedetect=noise={threshold}:d={min_silence_len}",
        "-f", "null", "-"
    ]
    
    result = subprocess.run(command_detect, stderr=subprocess.PIPE, text=True)
    output = result.stderr
    
    silence_starts = [float(x) for x in re.findall(r"silence_start: ([\d\.]+)", output)]
    silence_ends = [float(x) for x in re.findall(r"silence_end: ([\d\.]+)", output)]
    
    if len(silence_starts) > len(silence_ends):
        dur_cmd = ["ffmpeg", "-i", input_path, "-hide_banner"]
        dur_res = subprocess.run(dur_cmd, stderr=subprocess.PIPE, text=True)
        dur_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", dur_res.stderr)
        if dur_match:
            h, m, s = map(float, dur_match.groups())
            duration = h*3600 + m*60 + s
            silence_ends.append(duration)
        else:
            silence_starts = silence_starts[:len(silence_ends)]
            
    dur_cmd = ["ffmpeg", "-i", input_path, "-hide_banner"]
    dur_res = subprocess.run(dur_cmd, stderr=subprocess.PIPE, text=True)
    duration = 0
    dur_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", dur_res.stderr)
    if dur_match:
        h, m, s = map(float, dur_match.groups())
        duration = h*3600 + m*60 + s
    
    clips = []
    current_pos = 0.0
    
    for start, end in zip(silence_starts, silence_ends):
        if start > current_pos:
            clips.append((current_pos, start))
        current_pos = end
        
    if current_pos < duration:
        clips.append((current_pos, duration))
        
    if not clips:
        import shutil
        shutil.copy(input_path, output_path)
        return output_path
        
    filter_complex = ""
    for i, (start, end) in enumerate(clips):
        filter_complex += f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];"
        filter_complex += f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];"
        
    for i in range(len(clips)):
        filter_complex += f"[v{i}][a{i}]"
    
    filter_complex += f"concat=n={len(clips)}:v=1:a=1[outv][outa]"
    
    command = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        output_path
    ]
    
    subprocess.run(command, check=True)
    return output_path

def adjust_speed(input_path, output_path, speed=1.5):
    speed = max(0.5, min(speed, 2.0))
    
    command = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_path,
        "-filter_complex", f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
        "-map", "[v]", "-map", "[a]",
        output_path
    ]
    
    subprocess.run(command, check=True)
    return output_path

def trim_video(input_path, output_path, start_trim=0, end_trim=0):
    dur_cmd = ["ffmpeg", "-i", input_path, "-hide_banner"]
    dur_res = subprocess.run(dur_cmd, stderr=subprocess.PIPE, text=True)
    duration = 0
    dur_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", dur_res.stderr)
    if dur_match:
        h, m, s = map(float, dur_match.groups())
        duration = h*3600 + m*60 + s

    start_time = start_trim
    
    new_duration = duration - start_trim - end_trim
    
    if new_duration <= 0:
        import shutil
        shutil.copy(input_path, output_path)
        return output_path
        
    command = [
        "ffmpeg", "-y", "-nostdin",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(new_duration),
        "-c", "copy",
        output_path
    ]
    
    subprocess.run(command, check=True)
    return output_path

def add_captions(input_path, output_path, target_language=None):
    """
    Leverages Gemini API for high-speed transcription and translation.
    """
    srt_content = generate_srt_gemini(input_path, target_language)
    
    if srt_content.startswith("Error"):
        raise Exception(f"Caption Generation Failed: {srt_content}")

    # Use a fixed, space-free filename for the temporary SRT
    temp_srt_filename = f"temp_captions_{uuid.uuid4().hex[:8]}.srt"
    # Place SRT in current working directory (project root) to avoid path escaping issues
    temp_srt_path = temp_srt_filename
    
    with open(temp_srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    
    style = (
        "FontSize=18,"
        "PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=20"
    )
    
    # Use absolute paths for -i and output
    abs_input_path = os.path.abspath(input_path)
    abs_output_path = os.path.abspath(output_path)
    
    # Transform path for FFmpeg subtitles filter on Windows
    # FFmpeg's subtitles filter parser is notoriously picky on Windows.
    # We need to:
    # 1. Use absolute path.
    # 2. Replace backslashes with forward slashes.
    # 3. Escape the colon (e.g., C\:).
    # 4. Wrap the entire path in single quotes.
    abs_srt_path = os.path.abspath(temp_srt_path).replace("\\", "/")
    abs_srt_path = abs_srt_path.replace(":", "\\:")
    
    command = [
        "ffmpeg", "-y", "-nostdin",
        "-i", abs_input_path,
        "-vf", f"subtitles='{abs_srt_path}':force_style='{style}'",
        "-c:a", "copy",
        abs_output_path
    ]
    
    # Run FFmpeg from the current directory where the SRT file is located
    subprocess.run(command, check=True)
    
    # Clean up temporary SRT file
    try:
        if os.path.exists(temp_srt_path):
            os.remove(temp_srt_path)
    except Exception as e:
        print(f"Warning: Could not remove temp srt: {e}")
    
    return output_path

def get_speech_intervals_local(input_path):
    """
    Uses FFmpeg silencedetect to find speech intervals.
    A professional local fallback when AI is unavailable.
    """
    import subprocess
    import re

    # detect silence
    command = [
        "ffmpeg", "-i", input_path,
        "-af", "silencedetect=noise=-35dB:d=0.2",
        "-f", "null", "-"
    ]
    
    # Run synchronously to capture stderr where silencedetect outputs its data
    result = subprocess.run(command, capture_output=True, text=True, stderr=subprocess.STDOUT)
    output = result.stdout

    silence_starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", output)]
    silence_ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", output)]
    
    # Get total duration
    duration_match = re.search(r"Duration: (\d{2}:\d{2}:\d{2}.\d{2})", output)
    total_duration = 0.0
    if duration_match:
        h, m, s = duration_match.group(1).split(':')
        total_duration = int(h)*3600 + int(m)*60 + float(s)

    if not silence_starts:
        return [(0, total_duration)] if total_duration > 0 else []

    speech_intervals = []
    current_time = 0.0
    
    # Ensure silence_ends matches silence_starts length if loop is mid-parse
    num_pairs = min(len(silence_starts), len(silence_ends))
    
    for i in range(num_pairs):
        start = silence_starts[i]
        end = silence_ends[i]
        if start > current_time:
            speech_intervals.append((current_time, start))
        current_time = end
        
    if current_time < total_duration:
        speech_intervals.append((current_time, total_duration))
        
    return speech_intervals

def remove_noise(input_path, output_path):
    """
    Nuclear-Grade Speech Enhancement (MAX Aggressive):
    1. Stage 1: Plosive/Rumble Kill (Highpass 100Hz).
    2. Stage 2: Heavy Spectral Scrubbing (40dB Reduction).
    3. Stage 3: Non-linear Means Smoothing (Aggressive).
    4. Stage 4: Surgical Audio Gate (Aggressive Threshold).
    5. Stage 5: Speech Normalization (Consistent Levels).
    6. Stage 6: The Absolute Void Gate (AI-driven).
    """
    print(f"Deploying NUCLEAR-GRADE accuracy engine for {os.path.basename(input_path)}...")
    srt_content = generate_srt_gemini(input_path)
    
    # Nuclear Filter Chain for extreme noise environments
    # afftdn: nr=40 (very aggressive), nf=-20 (handles louder noise floor)
    # anlmdn: s=7 (strong smoothing)
    # agate: threshold=-28dB (standard gate)
    # speechnorm: ensures voice is prominent
    base_vocal_chain = (
        "highpass=f=100,"
        "afftdn=nr=40:nf=-25," 
        "anlmdn=s=7,"
        "agate=threshold=-30dB:ratio=20:attack=2:release=100,"
        "speechnorm=e=10:r=0.0001,"
        "lowpass=f=10000"
    )

    if srt_content.startswith("Error"):
        print("AI Gating Unavailable. Switching to Local-Mastery Silence Detection...")
        intervals = get_speech_intervals_local(input_path)
    else:
        import re
        timestamp_pattern = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})")
        intervals = []
        
        def to_sec(s):
            h, m, sm = s.split(":")
            sec, ms = sm.split(",")
            return int(h)*3600 + int(m)*60 + int(sec) + int(ms)/1000.0

        for line in srt_content.splitlines():
            match = timestamp_pattern.search(line)
            if match:
                start_str, end_str = match.groups()
                intervals.append((to_sec(start_str), to_sec(end_str)))
        
        if not intervals:
            af_filters = base_vocal_chain
        else:
            # Stage 6: The Void Gate
            conditions = "+".join([f"between(t,{s:.3f},{e:.3f})" for s, e in intervals])
            af_filters = f"{base_vocal_chain},volume='if({conditions},1,0)':eval=frame"

    print(f"DEBUG: Final Audio Filter String: '{af_filters}'")

    command = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_path,
        "-af", af_filters,
        "-vcodec", "copy",
        output_path
    ]
    
    subprocess.run(command, check=True)
    return output_path

def remove_background(input_path, output_path):
    """
    Pro-Grade Background Removal:
    1. Uses Rembg (U2Net/ONNX) for surgical subject isolation.
    2. Replaces background with pure solid chroma green (#00FF00).
    3. Merges audio back for a professional final clip.
    """
    from rembg import remove, new_session
    import cv2
    import numpy as np
    from PIL import Image

    # Initialize a persistent session for much faster frame processing
    print("Initializing AI Segmentation Engine (this may take a moment)...")
    session = new_session()

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception("Error: Could not open video file.")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Temporary path for video reconstruction
    temp_silent_path = os.path.join(os.path.dirname(output_path), f"temp_rembg_{os.path.basename(output_path)}")
    
    # Use cv2 + libx264 for high-quality intermediate
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_silent_path, fourcc, fps, (width, height))

    print(f"Executing Pro-Grade AI Isolation for {os.path.basename(input_path)}...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Convert BGR (cv2) to RGB (PIL/Rembg)
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img)
        
        # Apply Rembg with solid green background
        # bgcolor is RGBA: (red, green, blue, alpha)
        # We want pure green: (0, 255, 0, 255)
        isolated_pil = remove(pil_img, bgcolor=(0, 255, 0, 255), session=session)
        
        # Convert back to BGR for VideoWriter
        output_frame = cv2.cvtColor(np.array(isolated_pil), cv2.COLOR_RGBA2BGR)
        out.write(output_frame)

    cap.release()
    out.release()

    # Final FFmpeg pass: Restore audio and fix orientation/encoding
    try:
        command_merge = [
            "ffmpeg", "-y", "-nostdin",
            "-i", temp_silent_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-shortest",
            output_path
        ]
        subprocess.run(command_merge, check=True)
    except Exception as e:
        print(f"Merge Error: {e}")
        os.replace(temp_silent_path, output_path)
    finally:
        if os.path.exists(temp_silent_path):
            os.remove(temp_silent_path)

    return output_path

def resize_to_vertical(input_path, output_path):
    command = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_path,
        "-vf", "crop=ih*(9/16):ih",
        "-c:a", "copy",
        output_path
    ]
    
    subprocess.run(command, check=True)
    return output_path

def resize_to_horizontal(input_path, output_path):
    command = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_path,
        "-vf", "crop=iw:iw*(9/16)",
        "-c:a", "copy",
        output_path
    ]
    
    subprocess.run(command, check=True)
    return output_path

def extract_audio(input_path, output_path):
    base, _ = os.path.splitext(output_path)
    audio_output = base + ".mp3"
    
    command = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_path,
        "-vn", 
        "-acodec", "libmp3lame",
        "-q:a", "2", 
        audio_output
    ]
    
    subprocess.run(command, check=True)
    return audio_output

def summarize_video(input_path, output_path, user_prompt: str = ""):
    """
    Performs deep AI analysis using Gemini.
    """
    if not output_path.endswith(".txt"):
        base, _ = os.path.splitext(output_path)
        output_path = base + ".txt"

    ai_summary = generate_summary_gemini(input_path, user_prompt)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ai_summary)

    return output_path

def generate_new_video(output_path, prompt, model: str = 'veo-3.1-generate-preview'):
    """
    Generates a brand new video using Veo.
    """
    return generate_video_veo(prompt, output_path, model=model)

def remove_watermark(input_path, output_path, location="bottom_right", watermark_type="small_logo", custom_w=None, custom_h=None, strategy="heal"):
    """
    Advanced Watermark Removal:
    - "heal": Uses AI inpainting (OpenCV) with feathered edges.
    - "crop": Professional zero-blur edge removal (Best for corners).
    - "fast": Lightning-fast FFmpeg delogo.
    """
    if location is None:
        location = "bottom_right"
        
    import cv2
    import numpy as np
    import os
    import subprocess
    import uuid

    # 1. Get exact video dimensions
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception("Error: Could not open video file.")
    
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Orientation check
    is_vertical = h > w

    if strategy == "fast":
        print(f"DEBUG: Using Lightning-Fast Strategy for {location}...")
        # Resolve dimensions for FFmpeg
        if custom_w and custom_w > 0:
            logo_w = int(w * (custom_w / 100))
        elif "full_width" in location:
            logo_w = w
        elif "banner" in watermark_type:
            logo_w = int(w * 0.50)
        else:
            logo_w = int(w * 0.25) if is_vertical else int(w * 0.15)

        if custom_h and custom_h > 0:
            logo_h = int(h * (custom_h / 100))
        elif "banner" in watermark_type or "full_width" in location:
            logo_h = int(h * 0.12)
        else:
            logo_h = int(h * 0.10) if is_vertical else int(h * 0.08)

        x, y = 0, 0
        if "top" in location: y = 0
        elif "bottom" in location: y = h - logo_h
        elif "middle" in location or "center" in location or "full_width" in location:
            y = (h // 2) - (logo_h // 2)

        if "left" in location: x = 0
        elif "right" in location: x = w - logo_w
        elif "center" in location: x = (w // 2) - (logo_w // 2)
        elif "full_width" in location: x = 0

        # Safety Clamping for FFmpeg
        x = max(1, min(x, w - logo_w - 1))
        y = max(1, min(y, h - logo_h - 1))
        logo_w = max(1, min(logo_w, w - x - 1))
        logo_h = max(1, min(logo_h, h - y - 1))

        command = [
            "ffmpeg", "-y", "-nostdin",
            "-i", os.path.abspath(input_path),
            "-vf", f"delogo=x={x}:y={y}:w={logo_w}:h={logo_h}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy",
            os.path.abspath(output_path)
        ]
        subprocess.run(command, check=True)
        return output_path

    if strategy == "crop" and not any(k in location for k in ["center", "middle", "full_width"]):
        print(f"DEBUG: Using Pro-Crop Strategy for zero-blur removal at {location}...")
        # Crop logic: Remove 8-10% of the edge where the logo sits
        crop_w, crop_h = w, h
        x_offset, y_offset = 0, 0
        
        # Standard mobile watermark margin is about 8-10%
        margin_w = int(w * 0.12) # Increased for transparency
        margin_h = int(h * 0.10)

        # For corners, we just shift the window
        if "bottom" in location:
            crop_h = h - margin_h
            y_offset = 0
        elif "top" in location:
            crop_h = h - margin_h
            y_offset = margin_h
            
        if "right" in location:
            crop_w = w - margin_w
            x_offset = 0
        elif "left" in location:
            crop_w = w - margin_w
            x_offset = margin_w

        # FFmpeg crop + scale
        # crop=w:h:x:y
        command = [
            "ffmpeg", "-y", "-nostdin",
            "-i", os.path.abspath(input_path),
            "-vf", f"crop={crop_w}:{crop_h}:{x_offset}:{y_offset},scale={w}:{h}:flags=bicubic",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            os.path.abspath(output_path)
        ]
        subprocess.run(command, check=True)
        return output_path

    # If we are here, we use HEAL (Standard for middle/banners)
    print(f"DEBUG: Using AI Healing for {location} (Full-Width/Center detected)...")
    
    # 2. HEAL Strategy (with upgraded feathered edges)
    # Determine Dimensions
    if custom_w and custom_w > 0:
        logo_w = int(w * (custom_w / 100))
    elif "full_width" in location:
        logo_w = w
    elif "banner" in watermark_type:
        logo_w = int(w * 0.50)
    elif is_vertical:
        logo_w = int(w * 0.25)
    else:
        logo_w = int(w * 0.15)

    if custom_h and custom_h > 0:
        logo_h = int(h * (custom_h / 100))
    else:
        logo_h = int(h * 0.08)
    
    x, y = 0, 0
    if "top" in location: y = 0
    if "bottom" in location: y = h - logo_h
    if "left" in location: x = 0
    if "right" in location: x = w - logo_w
    if "center" in location:
        x, y = (w // 2) - (logo_w // 2), (h // 2) - (logo_h // 2)

    # Safety Clamping
    x = max(0, min(x, w - logo_w))
    y = max(0, min(y, h - logo_h))
    logo_w = min(logo_w, w - x)
    logo_h = min(logo_h, h - y)

    temp_processed_path = os.path.join(os.path.dirname(output_path), f"temp_heal_{uuid.uuid4().hex[:8]}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_processed_path, fourcc, fps, (w, h))

    # Create feathered mask
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y:y+logo_h, x:x+logo_w] = 255
    # Feather the mask slightly to prevent hard edges
    mask_blur = cv2.GaussianBlur(mask, (21, 21), 0)

    print(f"Executing AI HEAL (Feathered) for {int(cap.get(cv2.CAP_PROP_FRAME_COUNT))} frames...")
    
    frame_count = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Pre-calculate common alpha values
    alpha = mask_blur.astype(float) / 255.0
    alpha = cv2.merge([alpha, alpha, alpha])
    inv_alpha = 1.0 - alpha

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        if frame_count % 30 == 0:
            print(f"DEBUG: Healing Progress: {frame_count}/{total_frames} frames ({(frame_count/total_frames)*100:.1f}%)")

        # Healing
        healed = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
        
        # Alpha blend (Optimized with pre-calc)
        final_frame = (healed.astype(float) * alpha) + (frame.astype(float) * inv_alpha)
        out.write(final_frame.astype(np.uint8))
        frame_count += 1

    cap.release()
    out.release()

    # Final pass to restore audio
    try:
        command_merge = [
            "ffmpeg", "-y", "-nostdin",
            "-i", temp_processed_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-shortest",
            output_path
        ]
        subprocess.run(command_merge, check=True)
    except Exception as e:
        print(f"Healing Merge Error: {e}")
        os.replace(temp_processed_path, output_path)
    finally:
        if os.path.exists(temp_processed_path):
            os.remove(temp_processed_path)

    return output_path
