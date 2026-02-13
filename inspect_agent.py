
from effgen import Agent
import inspect

methods = inspect.getmembers(Agent, predicate=inspect.isfunction)
for name, func in methods:
    print(f"Method: {name}")
    print(f"Signature: {inspect.signature(func)}")
    print("-" * 20)
