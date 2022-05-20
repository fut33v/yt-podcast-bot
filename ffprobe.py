from typing import NamedTuple
import subprocess
import json

class FFProbeResult(NamedTuple):
    return_code: int
    json: str
    error: str


def ffprobe(file_path) -> FFProbeResult:
    command_array = ["ffprobe",
                     "-v", "quiet",
                     "-print_format", "json",
                     "-show_format",
                     "-show_streams",
                     file_path]
    result = subprocess.run(command_array, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return FFProbeResult(return_code=result.returncode,
                         json=result.stdout,
                         error=result.stderr)

def get_duration(input_file):
    ret = ffprobe(input_file)
    try:
        ffprobe_json = json.loads(ret.json)
    except json.JSONDecodeError:
        return None
    try:
        duration = int(float(ffprobe_json['format']['duration']))
    except KeyError:
        return None
    return duration