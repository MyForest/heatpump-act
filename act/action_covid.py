import datetime
from typing import Generator

import structlog

from .action import Action
from .device_infos import DeviceInfos
from .target_water_temperature import TargetWaterTemperature


# --------------------------------------------------------------------------------
class Covid:
    """Override the efficiency mechanims to ensure we are warm and have hot water. Notably this has an impact if the windows are open allowing for more fresh (cold) air"""

    @staticmethod
    def ensure_hot_water_available(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> Generator[Action, None, None]:
        latest_device_info = device_infos[-1]

        current_tank_temperature = float(latest_device_info["TankWaterTemperature"])

        desired = TargetWaterTemperature.target_tank_temperature(calculation_moment, device_infos)
        tolerable = desired - 8
        if current_tank_temperature > tolerable:
            structlog.get_logger().debug(
                "The tank temperature is higher than the tolerable temperature so we're going to leave it alone",
                current_tank_temperature=current_tank_temperature,
                tolerable=tolerable,
            )
            return

        structlog.get_logger().debug("We need to do something to heat the tank up")
        set_temperature = float(latest_device_info["SetTankWaterTemperature"])
        if desired > set_temperature:
            yield Action(
                "SetTankWaterTemperature",
                desired,
                f"The current target tank temperature is only {set_temperature} °C which is below the desired temperature of {desired} °C"
                + " so we're going to increase the desired temperature",
            )

        if not latest_device_info["Power"]:
            yield Action(
                "Power",
                "true",
                "Someone might need warm water",
            )

        if not latest_device_info["ForcedHotWaterMode"]:
            yield Action(
                "ForcedHotWaterMode",
                "true",
                f"Forcibly heat the water up because the hot water is only at {current_tank_temperature} °C",
            )

    @staticmethod
    def covid_mode_enabled(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ):
        return False

    @staticmethod
    def can_be_powered_off(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ):
        if calculation_moment.hour > 1 and calculation_moment.hour < 7:
            # Allow things to be more peaceful overnight
            return True

        return not Covid.covid_mode_enabled(calculation_moment, device_infos)

    @staticmethod
    def ensure_the_house_is_warm(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> Generator[Action, None, None]:
        latest_device_info = device_infos[-1]

        if not latest_device_info["Power"]:
            if not Covid.can_be_powered_off(calculation_moment, device_infos):
                yield Action(
                    "Power",
                    "true",
                    "Turning on so we can do some heating for COVID",
                )
