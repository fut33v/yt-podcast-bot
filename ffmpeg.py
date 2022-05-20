import subprocess
from typing import NamedTuple
import os


class FFMpegResult(NamedTuple):
    return_code: int
    result_string: str
    error: str


def ffmpeg(input_file, options, output_file) -> FFMpegResult:
    command_array = ["ffmpeg", "-y", "-hide_banner", "-i", input_file]
    command_array.extend(options)
    command_array.append(output_file)
    result = subprocess.run(command_array, universal_newlines=True, check=False)
    return result.returncode


def divide_audio_by_hour(input_file: str, duration: int) -> list:
    parts = int(duration / (60 * 60)) + 1
    parts_list = []
    for hour in range(parts):
        start_hour_string = str(hour)
        start_hour_string.zfill(2)
        end_hour_string = str(hour+1)
        end_hour_string.zfill(2)
        options = ["-ss", f"{start_hour_string}:00:00", "-to", f"{end_hour_string}:00:00", "-c", "copy"]
        path, ext = os.path.splitext(input_file)
        output_part_fname = f"{path}_part{hour}{ext}"
        ret_code = ffmpeg(input_file, options, output_part_fname)
        if ret_code != 0:
            return None
        parts_list.append(output_part_fname)
    return parts_list
