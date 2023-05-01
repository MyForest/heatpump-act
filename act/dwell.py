import datetime
import math

from .device_infos import DeviceInfos
from .effective_temperature import EffectiveTemperature


# --------------------------------------------------------------------------------
class Dwell:
    @staticmethod
    def turn_off_dwell(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:
        latest_device_info = device_infos[-1]

        outdoor_temperature = float(latest_device_info["OutdoorTemperature"])
        try:
            outdoor_temperature = EffectiveTemperature.apparent_temp(calculation_moment)
        except:
            pass

        return Dwell.turn_off_dwell_from_temperature(outdoor_temperature)

    @staticmethod
    def turn_off_dwell_from_temperature(temperature: float) -> float:
        dwell_time = 500.0

        # Reduce dwell time according to how warm it is
        adjustment = math.pow(abs(temperature), 2.5)
        adjustment = math.copysign(adjustment, temperature)
        dwell_time = dwell_time - adjustment
        dwell_time = max(120, dwell_time)
        dwell_time = min(900, dwell_time)

        return dwell_time

    @staticmethod
    def turn_on_dwell(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:
        outdoor_temperature = float(device_infos[-1]["OutdoorTemperature"])
        try:
            outdoor_temperature = EffectiveTemperature.apparent_temp(calculation_moment)
        except:
            pass

        dwell_time = 360.0
        hour = calculation_moment.hour
        if hour < 6:
            dwell_time = dwell_time * 2

        # Extend dwell time according to how warm it is
        adjustment = math.pow(abs(outdoor_temperature), 2.5)
        adjustment = math.copysign(adjustment, outdoor_temperature)
        dwell_time = dwell_time + adjustment
        dwell_time = max(0, dwell_time)
        dwell_time = min(900, dwell_time)

        return dwell_time
