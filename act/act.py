import datetime
import json
import logging
import os
import sys
from typing import Generator

import pytz
import structlog
import typer

from act.device_infos import DeviceInfo
from act.last_time_stamp import LastTimeStamp


class Act:
    def __init__(self) -> None:
        self.__configure__logging()

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
            logger = structlog.get_logger(self.__class__.__name__)
            logger.info(f"Running as though it is {local_dt}")
            if dry_run:
                logger.debug("Using dry run so will not send commands to heat pump")

            deviceInfos = list(self.__getLatestDeviceInfos(local_dt))
            deviceInfos.reverse()
            if deviceInfos:
                logger.debug("Latest device info", reading_timestamp=LastTimeStamp.lastTimeStampInUTC(deviceInfos[-1]).isoformat())

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
