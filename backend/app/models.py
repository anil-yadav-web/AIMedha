import re
from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator


class Notice(BaseModel):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    title: str = Field(min_length=1, max_length=200)
    publication_date: date
    content: str = Field(min_length=1, max_length=20000)
    category: str = Field(default='General', max_length=80)
    source_filename: str = Field(default='', max_length=200)
    topic: str = Field(default='', max_length=100)
    revises: list[str] = Field(default_factory=list, max_length=10)

    @field_validator('title', 'content')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Must not be blank')
        return value


class Collection(BaseModel):
    notices: list[Notice] = Field(min_length=10, max_length=10)

    @model_validator(mode='after')
    def check_links(self):
        by_id = {n.id: n for n in self.notices}
        if len(by_id) != len(self.notices):
            raise ValueError('Notice IDs must be unique')
        for notice in self.notices:
            for previous in notice.revises:
                if previous not in by_id or by_id[previous].publication_date >= notice.publication_date:
                    raise ValueError('Revisions must reference an existing earlier notice')
        return self


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)

    @field_validator('query')
    @classmethod
    def normalize(cls, value):
        value = re.sub(r'\s+', ' ', value).strip()
        if not value:
            raise ValueError('Please enter a question.')
        return value
