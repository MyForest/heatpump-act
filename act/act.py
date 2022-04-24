import datetime
import json
import logging
import os
import sys
from typing import Dict, Generator, Iterable, List

import pytz
import structlog
import typer

from act.action import Action
from act.action_ensure_zone1_flow_temperature_is_correct import EnsureZone1FlowTemperatureIsCorrect
from act.action_manage_power_state_for_space_heating import ManageSpaceHeatingPower
from act.action_manage_tank_temperature import ManageTankTemperature
from act.action_stop_forcing_hot_water import StopForcingHotWater
from act.action_turn_off_power import TurnOffPower
from act.action_turn_on_power import TurnOnPower
from act.alter_setting import AlterSetting
from act.device_infos import DeviceInfo, DeviceInfos
from act.effective_temperature import EffectiveTemperature
from act.last_time_stamp import LastTimeStamp
from act.predicate import Predicate
from act.simple_checks import SimpleChecks


class Act:
    def __init__(self) -> None:
        Act.__configure_logging()
        self.__logger = structlog.get_logger(self.__class__.__name__)

    def trigger_code_ql(self):
        if True:
            pass
        else:
            raise Exception("Should not get here")

    @staticmethod
    def __configure_logging():

        logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
        logging.getLogger("act").setLevel(logging.DEBUG)
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.CallsiteParameterAdder([structlog.processors.CallsiteParameter.MODULE, structlog.processors.CallsiteParameter.FUNC_NAME]),
                structlog.contextvars.merge_contextvars,
                structlog.processors.TimeStamper("iso"),
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

    def act(
        self,
        calculation_moment: str = typer.Option(
            default="now",
            help="Run as though it is this UTC moment in ISO8601 format.",
        ),
        dry_run: bool = typer.Option(
            default=False,
            help="Run without sending commands.",
        ),
    ):
        """
        Instruct the heatpump to perform actions.
        """

        if calculation_moment == "now":
            calculation_moment = datetime.datetime.utcnow().isoformat()[:19]

        calculation_moment_datetime = datetime.datetime.strptime(calculation_moment, "%Y-%m-%dT%H:%M:%S")
        local_time_zone = pytz.timezone("UTC")
        local_dt = local_time_zone.localize(calculation_moment_datetime)

        self.__logger.info("Calculation moment", calculation_moment=local_dt.isoformat())
        self.__logger.info("Units", time="Seconds", temperature="Celsius", power="Watts")
        if dry_run:
            self.__logger.debug("Using dry run so will not send commands to heat pump")

        device_infos = list(self.__get_latest_device_infos(local_dt))
        device_infos.reverse()
        if len(device_infos) == 0:
            self.__logger.exception("No device information files were found")

        now = datetime.datetime.utcnow()
        utc = pytz.timezone("UTC")
        utc_now = utc.localize(now)

        if (utc_now - local_dt).total_seconds() > 59:
            structlog.get_logger().debug("Older runs would not have had access to the very latest device info when they ran")
            device_infos = device_infos[:-1]

        self.describe_device_infos_being_operated_on(device_infos)

        self.__log_effective_temperature(local_dt)

        if not self.actions_should_be_blocked(device_infos):
            self.__logger.info("Actions were not blocked")
            non_conflicting_actions = list(self.get_non_conflicting_actions(local_dt, device_infos))
            self.__logger.debug("Non-conflicting actions", size=len(non_conflicting_actions))

            self.perform_actions(dry_run, device_infos, non_conflicting_actions)

    def change(self, dry_run: bool, action: Action):

        prefix = ""
        if dry_run:
            prefix = "DRY RUN: "

        self.__logger.info(f"{prefix}{action.message}")

        if not dry_run:
            AlterSetting().send_update_to_melcloud(action.name, str(action.value), action.message, action.source, shoosh=True)

    def perform_actions(
        self,
        dry_run: bool,
        device_infos: DeviceInfos,
        gathered_actions: List[Action],
    ) -> None:

        if gathered_actions:

            for action in gathered_actions:
                self.__logger.debug(f"{action.message} ({action.name} -> {action.value} from {action.source})")
                self.change(dry_run, action)
        else:
            self.__logger.debug("No actions desired by any of the providers")

    def actions_should_be_blocked(self, device_infos: DeviceInfos) -> bool:

        blockers: Iterable[Predicate[DeviceInfos]] = [
            SimpleChecks.is_holiday_mode_on,
            SimpleChecks.is_defrost_mode_on,
            SimpleChecks.is_heatpump_offline,
            SimpleChecks.are_device_infos_missing,
        ]

        for predicate in blockers:
            if predicate(device_infos):
                self.__logger.info("Predicate blocked actions", predicate=predicate.__name__)
                return True

            self.__logger.debug("Predicate will not block actions", predicate=predicate.__name__)

        return False

    def get_non_conflicting_actions(self, calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Generator[Action, None, None]:

        gathered_actions = self.gather_actions(calculation_moment, device_infos)

        actions_by_setting_name: Dict = {}

        for action in gathered_actions:
            action_name = action.name
            if action_name in actions_by_setting_name:
                new_value = action.value
                other_new_value = actions_by_setting_name[action_name].value
                if new_value != other_new_value:
                    raise Exception(
                        f"There are multiple agents trying to alter {action_name} with values of {new_value} and {other_new_value}."
                        + " The messages are '{action.message}' and '{actions_by_setting_name[action.name].message}'"
                    )
            else:
                actions_by_setting_name[action.name] = action
                yield action

    def gather_actions(self, calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Generator[Action, None, None]:

        action_providers = [
            TurnOffPower.turn_off_power,
            TurnOnPower.turn_on_power,
            StopForcingHotWater.stop_forcing_hot_water,
            ManageTankTemperature.manage_tank_temperature,
            ManageSpaceHeatingPower.manage,
            EnsureZone1FlowTemperatureIsCorrect.ensure_target_flow_temp_at_maximum,
        ]

        for action_provider in action_providers:
            try:
                generator = action_provider(calculation_moment, device_infos)
                if not generator is None:
                    actions = list(generator)
                    if actions:
                        for action in actions:
                            action.source = action_provider.__qualname__
                            yield action
                    else:
                        self.__logger.debug("No actions desired", action=action_provider.__qualname__)
                else:
                    self.__logger.debug("No actions desired", action=action_provider.__qualname__)
            except Exception as err:
                self.__logger.debug(err)
                # logging.error("Problem getting actions from " + actionProvider.__qualname__, err)
                raise

    def __log_effective_temperature(self, calculation_moment: datetime.datetime):
        try:
            effective_outdoor_temperature = EffectiveTemperature.apparent_temp(calculation_moment)
            self.__logger.debug("Effective outdoor temperature", effective_outdoor_temperature=effective_outdoor_temperature)
        except:
            self.__logger.exception("Unable to get effective outdoor temperature")

    def describe_device_infos_being_operated_on(self, device_infos):
        self.__logger.debug("Device infos being used", size=len(device_infos), newest=LastTimeStamp.last_time_stamp_in_utc(device_infos[-1]).isoformat())

    def __get_latest_device_infos(self, calculation_moment: datetime.datetime) -> Generator[DeviceInfo, None, None]:

        yield_counter = 600

        devices_folder = os.path.join("/state", "downloads", "raw")
        self.__logger.debug("Loading device info", source=devices_folder)

        for root, dirs, files in os.walk(devices_folder, topdown=True):
            dirs.sort(reverse=True)
            files.sort(reverse=True)
            device_files = [fileName for fileName in files if fileName.startswith("devices_")]
            for file in device_files:
                file_path = os.path.join(root, file)
                with open(file_path, encoding="utf-8") as devices:
                    try:
                        device_info: DeviceInfo = json.load(devices)[0]["Structure"]["Devices"][0]["Device"]
                    except:
                        continue

                    last_time_stamp = LastTimeStamp.last_time_stamp_in_utc(device_info)

                    if last_time_stamp <= calculation_moment:

                        try:
                            del device_info["ListHistory24Formatters"]
                        except:
                            pass

                        yield device_info
                        yield_counter += -1
                        if yield_counter <= 0:
                            return


if __name__ == "__main__":
    typer.run(Act().act)
