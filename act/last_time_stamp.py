import datetime
import logging
import datetime
import pytz
from .device_infos import DeviceInfo


# --------------------------------------------------------------------------------
class LastTimeStamp:
    @staticmethod
    def lastTimeStampInUTC(deviceInfo: DeviceInfo) -> datetime.datetime:
        local_time_zone_moment = datetime.datetime.strptime(deviceInfo["LastTimeStamp"], "%Y-%m-%dT%H:%M:%S")

        local_time_zone = pytz.timezone("Europe/London")
        # Doesn't seem to alter the result whatever we pass for is_dst
        local_dt = local_time_zone.localize(local_time_zone_moment)
        return local_dt.astimezone(pytz.utc)
