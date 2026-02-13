
from effgen.models.base import BaseModel
import inspect

methods = inspect.getmembers(BaseModel, predicate=inspect.isfunction)
for name, func in methods:
    print(f"Method: {name}")
    print(f"Signature: {inspect.signature(func)}")
    print("-" * 20)
