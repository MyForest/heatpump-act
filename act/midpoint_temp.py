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

        m = calculation_moment.month
        # Equation for Goole, United Kingdom: https://www.metoffice.gov.uk/research/climate/maps-and-data/uk-climate-averages/gcx4kb837
        return (0.0019 * m**5) + (-0.04973 * m**4) + (0.37424 * m**3) - (0.64667 * m**2) + (0.43078 * m) + 3.86
