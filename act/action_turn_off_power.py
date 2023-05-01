import datetime
from typing import Generator

import structlog

from .action import Action
from .action_turn_on_power import TurnOnPower
from .device_infos import DeviceInfos
from .temperature_thresholds import TemperatureThresholds


# --------------------------------------------------------------------------------
class TurnOffPower:
    @staticmethod
    def turn_off_power(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Generator[Action, None, None]:
        latest_device_info = device_infos[-1]

        if not latest_device_info["Power"]:
            return

        try:
            if TurnOnPower.should_turn_on_power(calculation_moment, device_infos):
                # Don't get into a fight
                return
        except StopIteration:
            pass

        if TurnOffPower.was_forced_hot_water(device_infos[-5:]):
            target_temperature = latest_device_info["SetTankWaterTemperature"]

            if target_temperature:
                current_tank_temperature = float(latest_device_info["TankWaterTemperature"])
                if current_tank_temperature:
                    if current_tank_temperature < (target_temperature - 2):
                        structlog.get_logger().debug(
                            "Not looking to turn off because the water was recently forced on but hasn't got near to the target temperature of "
                            + str(target_temperature)
                            + " °C yet. It's at "
                            + str(current_tank_temperature)
                            + " °C"
                        )
                        return

        was_recent_demand = TurnOffPower.was_demand(device_infos[-3:])
        was_demand_a_while_back = TurnOffPower.was_demand(device_infos[-6:-3])

        min_temp = TemperatureThresholds.min_flow_temp(calculation_moment, device_infos)
        current_flow = float(latest_device_info["FlowTemperature"])

        if was_demand_a_while_back and (not was_recent_demand):
            if current_flow > min_temp:
                yield Action(
                    "Power",
                    "false",
                    "The heat pump doesn't think it's worth continuing to generate heat so turning it off",
                )
            else:
                structlog.get_logger().debug(
                    "Even though the heatpump doesn't seem to want to do work at the moment, the flow is only "
                    + str(current_flow)
                    + " °C so not turning off because the min flow temp is "
                    + str(min_temp)
                    + " °C"
                )

    @staticmethod
    def was_stable_flow_temperature(device_infos: DeviceInfos) -> bool:
        recent_flow_temps = [float(deviceInfo["FlowTemperature"]) for deviceInfo in device_infos[-10:]]
        delta = max(recent_flow_temps) - min(recent_flow_temps)
        structlog.get_logger().debug("The flow temperature delta over the last readings in °C", size=len(recent_flow_temps), delta=delta)
        if max(recent_flow_temps) - min(recent_flow_temps) <= 1:
            return True
        return False

    @staticmethod
    def was_demand(device_infos: DeviceInfos) -> bool:
        return sum([float(device_info["HeatPumpFrequency"]) for device_info in device_infos]) != 0

    @staticmethod
    def was_forced_hot_water(device_infos: DeviceInfos) -> bool:
        forced_entries = [device_info for device_info in device_infos if device_info["ForcedHotWaterMode"]]
        return len(forced_entries) > 0
