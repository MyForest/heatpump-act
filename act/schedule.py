import datetime
import pytz
from typing import Optional

from crontab import CronTab

from .device_infos import DeviceInfos

# --------------------------------------------------------------------------------
class Schedule:
    @staticmethod
    def crontab() -> str:
        # Times in UTC
        return """
0 5 * * 1-5 On
30 7 * * 0,6 On

0 21 * * * Off
"""

    @staticmethod
    def off_job_name():
        return "Off"

    @staticmethod
    def on_job_name():
        return "On"

    @staticmethod
    def reason_to_turn_on(moment: datetime.datetime, device_infos: DeviceInfos) -> Optional[str]:
        """This is used to nudge the system into life depending on the temperature, the boosting and the time"""

        recentJob = Schedule.recent_job_moment(moment, Schedule.on_job_name())
        if recentJob:
            return f"Schedule requested to turn on at {recentJob.isoformat()}"

        return None

    @staticmethod
    def next_job_moment(moment: datetime.datetime, job_name: str) -> Optional[datetime.datetime]:

        file_cron = CronTab(tab=Schedule.crontab())

        jobs = file_cron.find_command(job_name)
        nextOnTimes = []
        # get_next doesn't include now if it's exactly the right time but we consider that we will act if it's the right time right now
        a_smidge_earlier = moment - datetime.timedelta(seconds=1)
        # tz = pytz.timezone("Europe/London")
        # local_date = a_smidge_earlier.astimezone(tz)

        # logging.debug("Looking for '" + jobName + "' jobs from " + local_date.isoformat())

        for job in jobs:
            schedule = job.schedule(date_from=a_smidge_earlier)

            nextRun = schedule.get_next()
            if nextRun:
                nextOnTimes.append(nextRun)

        if nextOnTimes:
            nextOnTimes.sort()
            return nextOnTimes[0]

        return None

    @staticmethod
    def recent_job_moment(moment: datetime.datetime, job_name: str, time_window=300) -> Optional[datetime.datetime]:

        file_cron = CronTab(tab=Schedule.crontab())

        jobs = file_cron.find_command(job_name)
        for job in jobs:
            schedule = job.schedule(date_from=moment)

            previousRun = schedule.get_prev()
            if (moment - previousRun).total_seconds() < time_window:
                return previousRun

        return None

    @staticmethod
    def previous_job(moment: datetime.datetime) -> str:

        oldMoment = datetime.datetime.min
        utc = pytz.timezone("UTC")
        oldMoment = utc.localize(oldMoment)

        oldJobName = None
        file_cron = CronTab(tab=Schedule.crontab())
        for job in file_cron.crons:
            schedule = job.schedule(date_from=moment)
            previousRun = schedule.get_prev()
            if previousRun > oldMoment:
                oldJobName = job.command
                oldMoment = previousRun

        if oldJobName:
            return oldJobName

        raise Exception(f"Unable to find a job scheduled before {moment}")
