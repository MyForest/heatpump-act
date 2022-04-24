from act.dwell import Dwell


def test_above_zero():

    assert Dwell.turn_off_dwell_from_temperature(5) > 0


def test_below_an_hour():

    assert Dwell.turn_off_dwell_from_temperature(5) < 3600


def test_shorter_when_hotter():

    assert Dwell.turn_off_dwell_from_temperature(15) < Dwell.turn_off_dwell_from_temperature(5)


def test_less_than_five_minutes_when_hot():

    assert Dwell.turn_off_dwell_from_temperature(15) < 300


def test_more_than_three_minutes_when_cold():

    assert Dwell.turn_off_dwell_from_temperature(5) > 180
