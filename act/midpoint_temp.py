import datetime

from .device_infos import DeviceInfos


# --------------------------------------------------------------------------------
class MidPointTemp:
    @staticmethod
    def midpoint_temp_for_month(
        calculation_moment: datetime.datetime,
        device_mnfos: DeviceInfos,
    ) -> float:
        # Magic numbers for polynomial using UK mid-point historic temps

        month = calculation_moment.month
        # Equation for Goole, United Kingdom: https://www.metoffice.gov.uk/research/climate/maps-and-data/uk-climate-averages/gcx4kb837
        return (0.0019 * month**5) + (-0.04973 * month**4) + (0.37424 * month**3) - (0.64667 * month**2) + (0.43078 * month) + 3.86
