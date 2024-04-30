from typing import (
    Generic,
    Type,
    TypeVar,
)

from orm import Base

Model = TypeVar('Model', bound=Base)


class AbstractRepository(Generic[Model]):
    model: Type[Model]
    
    def __init__(self, session):
        self.session = session
    
    @classmethod
    def create(cls, **kwargs) -> Model:
        instance = cls.model(**kwargs)
        return instance
    
    def get(self, **kwargs) -> Model:
        return self.session.query(self.model).filter_by(**kwargs).one()
    
    def get_or_create(self, query_options=None, **kwargs):
        query = self.session.query(self.model).filter_by(**kwargs)
        if query_options is not None:
            query = query.options(query_options)
        existing = query.one_or_none()
        if not existing:
            return self.__class__.create(**kwargs)
        return existing
    
    def get_id(self, **kwargs):
        return (
            self.session.query(self.model.id)
            .filter_by(**kwargs)
            .one()
        )[0]
    
    def get_all(self) -> list[Model]:
        return self.session.query(self.model).all()
    
    def get_all_by(self, order_by=None, **kwargs) -> list[Model]:
        return self.session.query(self.model).filter_by(**kwargs).order_by(order_by).all()
