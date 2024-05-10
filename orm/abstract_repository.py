from .base import Base


class AbstractRepository[Model: Base]:
    model: type[Model]
    
    def __init__(self, session):
        self.session = session
    
    @classmethod
    def create(cls, **kwargs) -> Model:
        instance = cls.model(**kwargs)  # pyright: ignore[reportGeneralTypeIssues]
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
        if not hasattr(self.model, "id"):
            raise AttributeError(f"Model {self.model.__name__} has no id attribute")
        
        return (
            self.session.query(self.model.id)  # pyright: ignore[reportAttributeAccessIssue]
            .filter_by(**kwargs)
            .one()
        )[0]
    
    def get_all(self) -> list[Model]:
        return self.session.query(self.model).all()
    
    def get_all_by(self, *args, order_by=None, **kwargs) -> list[Model]:
        return (self.session.query(self.model)
                .filter(*args)
                .filter_by(**kwargs)
                .order_by(order_by)
                .all())
