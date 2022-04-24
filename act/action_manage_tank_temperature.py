import datetime
import statistics
from typing import Generator

import structlog

from .action import Action
from .device_infos import DeviceInfos
from .last_time_stamp import LastTimeStamp
from .target_water_temperature import TargetWaterTemperature
from .temperature_thresholds import TemperatureThresholds


# --------------------------------------------------------------------------------
class ManageTankTemperature:
    @staticmethod
    def __when_was_target_set_above_threshold(device_infos: DeviceInfos, threshold: float) -> datetime.datetime:

        # Default to something
        latest_device_info = device_infos[-1]

        for info in reversed(device_infos):
            if float(info["SetTankWaterTemperature"]) < threshold:
                break
            latest_device_info = info

        return LastTimeStamp.last_time_stamp_in_utc(latest_device_info)

    @staticmethod
    def __was_recently_heating_water(device_infos: DeviceInfos) -> bool:

        # Even if not forced, we are willing to let it carry on if it's getting hotter
        hot_water_energy_used = sum([device_info["HotWaterEnergyConsumedRate1"] for device_info in device_infos])

        return hot_water_energy_used > 0

    @staticmethod
    def manage_tank_temperature(
        calculation_moment: datetime.datetime,
        device_infos: DeviceInfos,
    ) -> Generator[Action, None, None]:

        latest_device_info = device_infos[-1]

        current_target = float(latest_device_info["SetTankWaterTemperature"])
        if current_target >= TemperatureThresholds.shutdown_water_at_this_temperature():

            # Let's see if we should override this high temp
            batch_size = 10
            last_batch_targets = [float(device_info["SetTankWaterTemperature"]) for device_info in device_infos[-batch_size:]]

            # We use the mean because it can wobble about a bit and we don't want to be too reactive
            mean_tank_temperature = statistics.mean(last_batch_targets)
            when_was_target_set = ManageTankTemperature.__when_was_target_set_above_threshold(device_infos, TemperatureThresholds.legionella_tank_set_temp())

            if mean_tank_temperature >= TemperatureThresholds.shutdown_water_at_this_temperature():

                if ManageTankTemperature.__was_recently_heating_water(device_infos[-batch_size:]):
                    structlog.get_logger().debug("Water has been heated in the last batch of cycles so leaving it alone", batch_size=batch_size)
                    return

                # It's been running this way for a while and has had chance to respond
                if latest_device_info["ForcedHotWaterMode"]:
                    structlog.get_logger().debug(
                        "Hot water is being forced so leaving it alone", current_target=current_target, when_was_target_set=when_was_target_set.isoformat()
                    )
                    return

                # It's not heating the water now so we are free to take back control

            else:
                # It's only been there for a short time, the system maybe be getting going
                structlog.get_logger().debug(
                    "Hot water was recently pushed to the current target so leaving it alone whilst it gets on with that",
                    current_target=current_target,
                    when_was_target_set=when_was_target_set.isoformat(),
                )
                return

        flow_temperature = float(latest_device_info["FlowTemperature"])

        new_target = TargetWaterTemperature.target_tank_temperature(calculation_moment, device_infos)

        if new_target:
            if current_target != new_target:
                yield Action(
                    "SetTankWaterTemperature",
                    new_target,
                    f"The current target tank temperature is {current_target} °C so setting target temp of {new_target} °C. The flow is {flow_temperature} °C.",
                )
