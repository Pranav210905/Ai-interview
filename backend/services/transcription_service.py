import subprocess
import os
import shutil
import time
from pathlib import Path
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

def find_ffmpeg() -> str:
    """Find FFmpeg executable, checking PATH and common installation locations."""
    # First, try to find it in PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    
    # Check common Windows installation locations
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        # Check WinGet installation location (version-agnostic)
        winget_packages = Path(localappdata) / "Microsoft" / "WinGet" / "Packages"
        if winget_packages.exists():
            # Look for Gyan.FFmpeg package directory
            for package_dir in winget_packages.iterdir():
                if "Gyan.FFmpeg" in package_dir.name and package_dir.is_dir():
                    # Look for ffmpeg-*-full_build directories
                    for build_dir in package_dir.iterdir():
                        if "ffmpeg" in build_dir.name.lower() and "full_build" in build_dir.name.lower() and build_dir.is_dir():
                            ffmpeg_exe = build_dir / "bin" / "ffmpeg.exe"
                            if ffmpeg_exe.exists():
                                return str(ffmpeg_exe)
    
    # Check other common locations
    common_paths = [
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe"),
    ]
    
    for path in common_paths:
        if path.exists():
            return str(path)
    
    # If not found, return "ffmpeg" to get a proper error message
    return "ffmpeg"

def convert_to_wav(input_path: str) -> str:
    # Ensure input file exists
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input audio file not found: {input_path}")
    
    output_path = input_path.rsplit(".", 1)[0] + ".wav"
    
    # Find FFmpeg executable
    ffmpeg_cmd = find_ffmpeg()

    try:
        result = subprocess.run([
            ffmpeg_cmd, "-i", input_path, "-ar", "16000", "-ac", "1", "-y", output_path
        ], check=True, capture_output=True, text=True)
        return output_path
    except FileNotFoundError:
        raise Exception(
            "FFmpeg not found. Please install FFmpeg and add it to your system PATH. "
            "Download from https://ffmpeg.org/download.html or install using: winget install Gyan.FFmpeg"
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise Exception(f"FFmpeg conversion failed: {error_msg}")

def transcribe_audio(audio_path: str) -> str:
    # Ensure audio file exists
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    wav_path = audio_path
    wav_created = False
    
    try:
        if not audio_path.endswith(".wav"):
            wav_path = convert_to_wav(audio_path)
            wav_created = True
            # Ensure converted file exists
            if not os.path.exists(wav_path):
                raise FileNotFoundError(f"Converted WAV file not found: {wav_path}")

        # Transcribe with error handling
        try:
            segments, info = model.transcribe(wav_path, beam_size=5)
            transcript = " ".join([segment.text for segment in segments])
        except Exception as e:
            raise Exception(f"Whisper transcription failed: {str(e)}")
        
        return transcript.strip()
        
    finally:
        # Clean up converted file if it was created
        if wav_created and wav_path != audio_path and os.path.exists(wav_path):
            max_cleanup_retries = 3
            for retry in range(max_cleanup_retries):
                try:
                    os.remove(wav_path)
                    break  # Successfully removed
                except (OSError, PermissionError) as e:
                    if retry == max_cleanup_retries - 1:
                        # Last retry failed - log but don't raise
                        print(f"Warning: Could not clean up temporary WAV file {wav_path}: {str(e)}")
                    else:
                        time.sleep(0.1 * (retry + 1))  # Brief wait before retry
                except Exception:
                    # Other errors - just ignore
                    break
