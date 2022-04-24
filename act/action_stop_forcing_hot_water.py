import datetime
from typing import Generator

from .action import Action
from .device_infos import DeviceInfos
from .schedule import Schedule
from .temperature_thresholds import TemperatureThresholds


# --------------------------------------------------------------------------------
class StopForcingHotWater:
    @staticmethod
    def stop_forcing_hot_water(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> Generator[Action, None, None]:

        device_info = device_infos[-1]

        if not device_info["ForcedHotWaterMode"]:
            return

        tank_temp = float(device_info["TankWaterTemperature"])
        current_target = float(device_info["SetTankWaterTemperature"])

        if tank_temp >= current_target:

            yield Action(
                "ForcedHotWaterMode",
                False,
                f"The tank temperature is{tank_temp} °C which is at least as hot as the target of {current_target} °C so stopping forced hot water mode",
            )

            if Schedule.previous_job(calculation_moment) == Schedule.off_job_name():
                yield Action(
                    "Power",
                    False,
                    "Heat pump was previously turned off by a schedule so revert to being off",
                )

        shutdown_temp = TemperatureThresholds.shutdown_water_at_this_temperature()
        if tank_temp >= shutdown_temp:
            yield Action(
                "ForcedHotWaterMode",
                False,
                f"The tank temperature is {tank_temp} °C which is at least as hot as the shutdown temperature of {shutdown_temp} °C so stopping forced hot water mode",
            )
