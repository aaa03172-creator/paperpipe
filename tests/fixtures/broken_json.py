case_hansson_truncated = """
Here is the result:
{
  "hard_tags": {"species": "human", "sample_size": 72, "model": null},
  "soft_tags": ["#Clinical", "#MCI"],
  "evidence_span": "Participants with MCI showed improvement."
"""

case_markdown = """
```json
{
  "hard_tags": {"species": "human", "sample_size": 40, "model": null},
  "soft_tags": ["#Clinical"],
  "confidence": 0.87
}
```
"""

case_python_style = """
{'hard_tags': {'species': None, 'sample_size': 12, 'model': '5xFAD'}, 'soft_tags': ['#Mechanism'], 'confidence': 0.71}
"""

case_trailing_commas = """
{
  "hard_tags": {"species": "mouse", "sample_size": 18, "model": "APP/PS1",},
  "soft_tags": ["#Preclinical",],
  "confidence": 0.66,
}
"""

case_chatter_with_json = """
Sure, here is the JSON you asked for.
{
  "hard_tags": {"species": "human", "sample_size": 58, "model": null},
  "soft_tags": ["#Nutrition", "#Clinical/MCI"],
  "confidence": 0.91
}
Let me know if you want a summary.
"""
