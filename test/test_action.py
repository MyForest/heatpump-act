import dataclasses
import json

from act.action import Action


def test_literal_read():
    action = Action(name="a name", value="a value", message="A message")
    assert action.name == "a name"
    assert action.value == "a value"
    assert action.message == "A message"


def test_positional_creation():
    action = Action("a name", "a value", "A message")
    assert action.name == "a name"


def test_to_json():
    action = Action("a name", "a value", "A message")
    assert json.dumps(dataclasses.asdict(action)) == '{"name": "a name", "value": "a value", "message": "A message", "source": "Unknown"}'
