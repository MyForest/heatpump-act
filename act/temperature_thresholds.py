import datetime

from .device_infos import DeviceInfos
from .effective_temperature import EffectiveTemperature


class TemperatureThresholds:
    @staticmethod
    def average_outdoor_temperature(device_infos: DeviceInfos) -> float:

        recentDeviceInfos = device_infos[-10:]

        total = sum([float(deviceInfo["OutdoorTemperature"]) for deviceInfo in recentDeviceInfos])
        return total / len(recentDeviceInfos)

    @staticmethod
    def max_flow_temp(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:

        effectiveOutdoorTemperature = device_infos[-1]["OutdoorTemperature"]
        try:
            effectiveOutdoorTemperature = EffectiveTemperature.apparent_temp(calculation_moment)
        except:
            pass

        if effectiveOutdoorTemperature < -15:
            return 50

        # -2x/3 + 40 =y
        # 15 => 30
        # 0 => 40
        # -15 => 50

        # 2020-01-30 Reducing top from 40 to 38 now we have longer, gentler heating
        # 2020-02-29 Reducing top from 40 to 38 now we have longer, gentler heating (doing it again, must have upped it one day)
        # 2020-03-02 Bumping back up to 40, Carey was cold this morning
        # 2020-03-05 Bumping back to 38 now I found it wasn't using the effective temp
        # 2020-12-25 Reducing uplift from 4 to 2 to make it run more gently
        # 2021-01-03 Increasing uplift from 2 to 4 because Carey is cold

        compCurveValue = int(38 - 2 * effectiveOutdoorTemperature / 3)
        ensureNotTooHigh = min(compCurveValue, 50)
        ensureNotTooLow = max(
            ensureNotTooHigh,
            TemperatureThresholds.min_flow_temp(calculation_moment, device_infos),
        )
        intended = ensureNotTooLow + 4
        return intended

    @staticmethod
    def min_flow_temp(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:

        effectiveOutdoorTemperature = device_infos[-1]["OutdoorTemperature"]
        try:
            effectiveOutdoorTemperature = EffectiveTemperature.apparent_temp(calculation_moment)
        except:
            pass

        if effectiveOutdoorTemperature > 15:
            return 25

        # -x/3 + 30 =y
        # 15 => 25
        # 0 => 30
        # -15 => 35

        compCurveValue = int(30 - effectiveOutdoorTemperature / 3)
        ensureNotTooHigh = min(compCurveValue, 35)
        ensureNotTooLow = max(ensureNotTooHigh, 25)
        return ensureNotTooLow

    @staticmethod
    def no_heating_required(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:
        """The sort of temperature that would prompt you to put on a jumper"""
        return 14

    @staticmethod
    def nice_shower_water_temp_in_summer() -> float:
        return 38

    @staticmethod
    def a_little_bit_cold_outdoor_temp() -> float:
        """The sort of temperature that would prompt you to put on a coat"""
        return 11

    @staticmethod
    def quite_cold_outdoor_temp() -> float:
        """The sort of temperature that would prompt you to put on a hat"""
        return 7

    @staticmethod
    def temperature_flexibility(device_info: dict) -> float:
        return 3

    @staticmethod
    def min_tank_set_temp() -> float:
        return 10

    @staticmethod
    def legionella_tank_set_temp() -> float:
        # Asking it to go to 55 just causes it to give up at 50
        return 60

    @staticmethod
    def shutdown_water_at_this_temperature() -> float:
        return 55

    @staticmethod
    def maxTankSetTemp() -> float:
        return 60
