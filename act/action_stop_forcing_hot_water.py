import datetime

from typing import Generator

from .temperature_thresholds import TemperatureThresholds
from .schedule import Schedule
from .action import Action
from .device_infos import DeviceInfos

# --------------------------------------------------------------------------------
class StopForcingHotWater:
    @staticmethod
    def stop_forcing_hot_water(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> Generator[Action, None, None]:

        deviceInfo = device_infos[-1]

        if not deviceInfo["ForcedHotWaterMode"]:
            return

        tankTemp = float(deviceInfo["TankWaterTemperature"])
        currentTarget = float(deviceInfo["SetTankWaterTemperature"])

        if tankTemp >= currentTarget:

            yield Action(
                "ForcedHotWaterMode",
                False,
                f"The tank temperature is{tankTemp} °C which is at least as hot as the target of {currentTarget} °C so stopping forced hot water mode",
            )

            if Schedule.previous_job(calculation_moment) == Schedule.off_job_name():
                yield Action(
                    "Power",
                    False,
                    "Heat pump was previously turned off by a schedule so revert to being off",
                )

        shutdownTemp = TemperatureThresholds.shutdown_water_at_this_temperature()
        if tankTemp >= shutdownTemp:
            yield Action(
                "ForcedHotWaterMode",
                False,
                f"The tank temperature is {tankTemp} °C which is at least as hot as the shutdown temperature of {shutdownTemp} °C so stopping forced hot water mode",
            )
