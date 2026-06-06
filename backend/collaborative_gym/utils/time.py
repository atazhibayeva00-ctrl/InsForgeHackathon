import time
from datetime import UTC, datetime, timedelta


def get_formatted_local_time():
    timestamp = time.time()
    local_time = time.localtime(timestamp)
    return time.strftime("%Y-%m-%d %H:%M:%S", local_time)


def get_utc_time_with_offset(offset):
    current_utc_time = datetime.now(UTC)
    offset_time = current_utc_time + timedelta(hours=offset)
    return offset_time.strftime("%Y-%m-%d %H:%M:%S")
