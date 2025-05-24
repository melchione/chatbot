from pydantic import Field
from datetime import datetime
from shared.orm.orm_entity import OrmEntity
from surrealdb import RecordID


class SyntheticText(OrmEntity):
    id: str | None | RecordID = Field(default=None, description="The surrealdb id")
    text: str = Field(description="The text of the synthetic text")
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="The datetime when the synthetic text was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="The datetime when the synthetic text was updated",
    )
