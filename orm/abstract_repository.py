from typing import (
    Generic,
    TypeVar,
)

from orm import Base

T = TypeVar('T', bound=Base)


class AbstractRepository(Generic[T]):
    model: T = None
    
    def __init__(self, session):
        self.session = session
    
    def get(self, **kwargs) -> T:
        return self.session.query(self.model).filter_by(**kwargs).one()
    
    def get_or_create(self, query_options=None, **kwargs) -> T:
        query = self.session.query(self.model).filter_by(**kwargs)
        if query_options is not None:
            query = query.options(query_options)
        existing = query.one_or_none()
        if not existing:
            return self.create(**kwargs)
        return existing
    
    def get_id(self, **kwargs):
        return (
            self.session.query(self.model.id)
            .filter_by(**kwargs)
            .one()
        )[0]
    
    def create(self, **kwargs) -> T:
        instance = self.model(**kwargs)
        self.session.add(instance)
        return instance
    
    def get_all(self) -> list[T]:
        return self.session.query(self.model).all()
    
    def get_all_by(self, order_by=None, **kwargs) -> list[T]:
        return self.session.query(self.model).filter_by(**kwargs).order_by(order_by).all()
