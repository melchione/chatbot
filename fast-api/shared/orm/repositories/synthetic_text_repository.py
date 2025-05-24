from typing import Any
from shared.orm.orm_repository import OrmRepository


class SyntheticTextRepository(OrmRepository):
    def __init__(self, /, **data: Any):
        super().__init__(**data)
