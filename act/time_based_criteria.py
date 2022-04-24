import datetime

# --------------------------------------------------------------------------------
class TimeBasedCriteria:
    @staticmethod
    def warm_part_of_day(calculation_moment: datetime.datetime) -> bool:
        hour = calculation_moment.hour
        after_starts_getting_warm = hour >= 10
        before_starts_getting_cold = hour <= 16
        return after_starts_getting_warm and before_starts_getting_cold
