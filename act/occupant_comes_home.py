import datetime

from .device_infos import DeviceInfos
from .effective_temperature import EffectiveTemperature


# --------------------------------------------------------------------------------
class OccupantComesHome:
    @staticmethod
    def needs_to_be_warmer(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> bool:

        device_info = device_infos[-1]

        outdoor_temperature = device_info["OutdoorTemperature"]
        try:
            outdoor_temperature = EffectiveTemperature.apparent_temp(calculation_moment)
        except:
            pass

        if outdoor_temperature > 15:
            return False

        if calculation_moment.weekday() < 5:
            if (calculation_moment.hour == 16) and calculation_moment.minute > 30 and calculation_moment.minute < 59:

                return_temperature = float(device_info["ReturnTemperature"])

                desired = 28

                if return_temperature < desired:
                    return True

        return False
