import datetime

from .device_infos import DeviceInfos

# --------------------------------------------------------------------------------
class OctopusGo:
    @staticmethod
    def power_will_be_cheap_for_next_fifteen_minutes(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> bool:
        # Yep, just a boolean on the simple tarriff

        if calculation_moment.hour == 0 and calculation_moment.minute > 30:
            return True

        if calculation_moment.hour in [1, 2, 3]:
            return True

        if calculation_moment.hour == 4 and calculation_moment.minute < 15:
            return True

        return False
