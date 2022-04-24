import datetime

import structlog

from .action_octopus_go import OctopusGo
from .device_infos import DeviceInfos
from .midpoint_temp import MidPointTemp
from .temperature_thresholds import TemperatureThresholds
from .time_based_criteria import TimeBasedCriteria


class TargetWaterTemperature:
    @staticmethod
    def tank_temperature_to_trigger_hot_water(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:
        """Only turn on the water if it goes below this temp"""

        desired_water_temperature = TargetWaterTemperature.target_tank_temperature(calculation_moment, device_infos)

        latest_device_info = device_infos[-1]
        flow_temp = float(latest_device_info["FlowTemperature"])
        power_is_on = latest_device_info["Power"]

        # Go just because the flow is really hot
        if flow_temp >= desired_water_temperature:
            # Don't just keep coming on all the time, we'll keep doing 2 minutes of water heating
            structlog.get_logger().debug("Let the tank drop a bit below the target")
            return desired_water_temperature - 10

        midpoint_temp = MidPointTemp.midpoint_temp_for_month(calculation_moment, device_infos)

        if midpoint_temp > TemperatureThresholds.quite_cold_outdoor_temp() and midpoint_temp < TemperatureThresholds.no_heating_required(calculation_moment, device_infos):
            # Always warm straight back up when someone has a shower
            structlog.get_logger().debug(
                "The outdoor temperature is warmer than the quiteColdOutdoorTemp. The hot water not likely to be heated by the space heating or solar diverter"
            )
            # When it's hotter than this we usually have some solar diverter action
            return desired_water_temperature - 15

        if power_is_on and TimeBasedCriteria.warm_part_of_day(calculation_moment):
            structlog.get_logger().debug("The power is on and it's a warm part of the day")
            return desired_water_temperature - 10

        if OctopusGo.power_will_be_cheap_for_next_fifteen_minutes(calculation_moment, device_infos):
            structlog.get_logger().debug("Power will be cheap for a while")
            return desired_water_temperature - 10

        structlog.get_logger().debug("Flow is colder than the desired water temp")
        # If the flow is quite a bit warmer than the tank then still plough ahead
        # If the flow is cold, don't do anything even if the tank is way colder than we'd like
        # Eventually some space heating will lift the flow and then we'll do the hot water

        return flow_temp - 20

    @staticmethod
    def increase_tank_temperature_if_it_is_cold_outside(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:

        # It's tempting to say "if it's cold now then make the target temp higher so the humans are warmer in the shower"
        # but that will cause it to be more likely to come on when it's cold during the night when it's inefficient and humans aren't using it anyway
        # You really want a "will the air be cold when the humans shower" but for that you'd need a weather forecast and to know when they might shower
        # So for now we can use the month as a proxy for that information

        midpoint_temp = MidPointTemp.midpoint_temp_for_month(calculation_moment, device_infos)

        if midpoint_temp < TemperatureThresholds.a_little_bit_cold_outdoor_temp():
            # A bit warmer around Winter
            return 1

        if midpoint_temp < TemperatureThresholds.quite_cold_outdoor_temp():
            # Make the water even warmer in the Winter for the humans
            return 2

        return 0

    @staticmethod
    def target_tank_temperature(calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> float:

        desired_water_temperature = TemperatureThresholds.nice_shower_water_temp_in_summer()

        desired_water_temperature += TargetWaterTemperature.increase_tank_temperature_if_it_is_cold_outside(calculation_moment, device_infos)

        return desired_water_temperature
