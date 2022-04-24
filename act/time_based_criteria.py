import datetime

# --------------------------------------------------------------------------------
class TimeBasedCriteria:
    @staticmethod
    def warm_part_of_day(calculation_moment: datetime.datetime) -> bool:
        hour = calculation_moment.hour
        return hour >= 10 and hour <= 16
