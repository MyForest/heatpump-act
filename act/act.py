import datetime
import json
import logging
import os
import sys
from typing import Dict, Generator, Iterable

import pytz
import structlog
import typer
from act.action import Action
from act.action_stop_forcing_hot_water import StopForcingHotWater

from act.device_infos import DeviceInfo, DeviceInfos
from act.effective_temperature import EffectiveTemperature
from act.last_time_stamp import LastTimeStamp
from act.predicate import Predicate
from act.simple_checks import SimpleChecks


class Act:
    def __init__(self) -> None:
        self.__configure__logging()
        self.__logger = structlog.get_logger(self.__class__.__name__)

    def __configure__logging(self):

        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.DEBUG,
        )
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.CallsiteParameterAdder([structlog.processors.CallsiteParameter.MODULE, structlog.processors.CallsiteParameter.FUNC_NAME]),
                structlog.contextvars.merge_contextvars,
                structlog.processors.TimeStamper(),
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

        with structlog.contextvars.bound_contextvars(calculation_moment=local_dt.isoformat()):

            self.__logger.info(f"Calculation moment is {local_dt}")
            if dry_run:
                self.__logger.debug("Using dry run so will not send commands to heat pump")

            device_infos = list(self.__getLatestDeviceInfos(local_dt))
            device_infos.reverse()
            if len(device_infos) == 0:
                self.__logger.exception("No device information files were found")

            now = datetime.datetime.utcnow()
            utc = pytz.timezone("UTC")
            utc_now = utc.localize(now)

            if (utc_now - local_dt).total_seconds() > 59:
                logging.debug("Older runs would not have had access to the very latest device info when they ran")
                device_infos = device_infos[:-1]

            self.describe_device_infos_being_operated_on(device_infos)

            self.__log_effective_temperature(local_dt)

            if not self.actions_should_be_blocked(device_infos):
                self.__logger.info("Actions were not blocked")
                nonConflictingActions = list(self.get_non_conflicting_actions(local_dt, device_infos))
                self.__logger.debug("Non-conflicting actions", size=len(nonConflictingActions))

    def actions_should_be_blocked(self, device_infos: DeviceInfos) -> bool:

        blockers: Iterable[Predicate[DeviceInfos]] = [
            SimpleChecks.is_holiday_mode_on,
            SimpleChecks.is_defrost_mode_on,
            SimpleChecks.is_heatpump_offline,
            SimpleChecks.are_device_infos_missing,
        ]

        for predicate in blockers:
            if predicate(device_infos):
                self.__logger.info(f"Predicate blocked actions", predicate=predicate.__name__)
                return True
            else:
                self.__logger.debug(f"Predicate will not block actions", predicate=predicate.__name__)

        return False

    def get_non_conflicting_actions(self, calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Generator[Action, None, None]:

        gatheredActions = self.gather_actions(calculation_moment, device_infos)

        actionsBySettingName: Dict = {}

        for action in gatheredActions:
            actionName = action.name
            if actionName in actionsBySettingName:
                newValue = action.value
                otherNewValue = actionsBySettingName[actionName].value
                if newValue != otherNewValue:
                    raise Exception(
                        f"There are multiple agents trying to alter {actionName} with values of {newValue} and {otherNewValue}. The messages are '{action.message}' and '{actionsBySettingName[action.name].message}'"
                    )
            else:
                actionsBySettingName[action.name] = action
                yield action

    def gather_actions(self, calculation_moment: datetime.datetime, device_infos: DeviceInfos) -> Generator[Action, None, None]:

        actionProviders = [
            StopForcingHotWater.stop_forcing_hot_water,
        ]

        for actionProvider in actionProviders:
            try:
                generator = actionProvider(calculation_moment, device_infos)
                if generator:
                    actions = list(generator)
                    if actions:
                        for action in actions:
                            action.source = actionProvider.__qualname__
                            yield action
                    else:
                        self.__logger.debug(f"No actions desired", action=actionProvider.__qualname__)
                else:
                    self.__logger.debug(f"No actions desired", action=actionProvider.__qualname__)
            except Exception as err:
                self.__logger.debug(err)
                # logging.error("Problem getting actions from " + actionProvider.__qualname__, err)
                raise

    def __log_effective_temperature(self, calculationMoment: datetime.datetime):
        try:
            effectiveOutdoorTemperature = EffectiveTemperature.apparent_temp(calculationMoment)
            self.__logger.debug(f"The effective outdoor temperature is {effectiveOutdoorTemperature} °C")
        except:
            self.__logger.exception("Unable to get effective temp")
            pass

    def describe_device_infos_being_operated_on(self, device_infos):
        self.__logger.debug(
            f"Operating on {len(device_infos)} device infos. The newest of which has a last time stamp of {LastTimeStamp.lastTimeStampInUTC(device_infos[-1]).isoformat()}"
        )

    def __getLatestDeviceInfos(self, calculationMoment: datetime.datetime) -> Generator[DeviceInfo, None, None]:

        yieldCounter = 600

        devicesFolder = os.path.join("/state", "downloads", "raw")
        logging.debug("Loading device info from " + devicesFolder)

        for root, dirs, files in os.walk(devicesFolder, topdown=True):
            dirs.sort(reverse=True)
            files.sort(reverse=True)
            deviceFiles = [fileName for fileName in files if fileName.startswith("devices_")]
            for file in deviceFiles:
                filePath = os.path.join(root, file)
                with open(filePath, encoding="utf-8") as devices:
                    try:
                        deviceInfo: DeviceInfo = json.load(devices)[0]["Structure"]["Devices"][0]["Device"]
                    except:
                        continue

                    lastTimeStamp = LastTimeStamp.lastTimeStampInUTC(deviceInfo)

                    if lastTimeStamp <= calculationMoment:

                        try:
                            del deviceInfo["ListHistory24Formatters"]
                        except:
                            pass

                        yield deviceInfo
                        yieldCounter += -1
                        if yieldCounter <= 0:
                            return


if __name__ == "__main__":
    typer.run(Act().act)
