import datetime

import pytz

from .device_infos import DeviceInfo


# --------------------------------------------------------------------------------
class LastTimeStamp:
    @staticmethod
    def last_time_stamp_in_utc(device_info: DeviceInfo) -> datetime.datetime:
        local_time_zone_moment = datetime.datetime.strptime(device_info["LastTimeStamp"], "%Y-%m-%dT%H:%M:%S")

        local_time_zone = pytz.timezone("Europe/London")
        # Doesn't seem to alter the result whatever we pass for is_dst
        local_dt = local_time_zone.localize(local_time_zone_moment)
        return local_dt.astimezone(pytz.utc)
