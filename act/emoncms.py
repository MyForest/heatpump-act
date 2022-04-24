import datetime
import json
import os
import pprint

import urllib3
from dotenv import load_dotenv

load_dotenv()
# --------------------------------------------------------------------------------
class EmonCMS:
    @staticmethod
    def get_feed_values(feed_id: int, moment: datetime.datetime = datetime.datetime.utcnow(), duration: int = 300, interval: int = 10):

        http = urllib3.PoolManager()

        start = (moment.timestamp() - duration) * 1000
        end = moment.timestamp() * 1000

        url = (
            os.environ["EMONCMS_URL"]
            + "feed/data.json?id="
            + str(feed_id)
            + "&apikey="
            + os.environ["EMONCMS_API_KEY"]
            + "&start="
            + str(start)
            + "&end="
            + str(end)
            + "&interval="
            + str(interval)
        )
        response = http.request("GET", url, timeout=5)

        j = json.loads(response.data.decode("utf-8"))
        if j:
            result = []
            for discovered_moment, value in j:
                if value is None:
                    pass
                else:
                    result.append({"time": discovered_moment, "value": float(value)})

            if result:
                return result

        raise Exception("No results")

    @staticmethod
    def get_feed_value(feed_id: int, moment: datetime.datetime = datetime.datetime.utcnow()):
        values = EmonCMS.get_feed_values(feed_id, moment, 300, 10)
        return values[-1]


# --------------------------------------------------------------------------------
def main():
    window = 24 * 3600
    result = EmonCMS.get_feed_values(os.environ["EMONCMS_SOLAR_FEED_ID"], datetime.datetime.utcnow() - datetime.timedelta(seconds=window), window, 30)

    pprint.pprint(result)


# ----------------------------------------
if __name__ == "__main__":
    main()
