
from effgen.tools.builtin import Retrieval
import inspect

methods = inspect.getmembers(Retrieval, predicate=inspect.isfunction)
for name, func in methods:
    print(f"Method: {name}")
    print(f"Signature: {inspect.signature(func)}")
    print("-" * 20)
