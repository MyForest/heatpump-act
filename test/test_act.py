from datetime import datetime
from act.act import Act


class TestAct:
    def test_something(self):
        Act().act(datetime.utcnow().isoformat()[:19])
