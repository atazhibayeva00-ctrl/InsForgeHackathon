from typing import Any

from aact.messages import DataModelFactory, DataModel


@DataModelFactory.register("json_obj")
class JsonObj(DataModel):
    object: dict[str, Any]
