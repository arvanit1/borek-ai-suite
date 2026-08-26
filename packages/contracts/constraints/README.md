# Layout constraint configs (BT-15, JJ-10, MS-12)

Per-layout content limits for the **AT-7 generic constraint validator** (`apps/api/services/validation/constraint_validator.py`).

Technical plan section 15 defines limits such as phase counts and string max lengths. Those limits are **data** in this directory (`group_a.yaml`, `group_b.yaml`, `group_c.yaml`). The validator interprets configs generically — no layout-specific Python code.

`group_a.yaml`, `group_b.yaml`, and `group_c.yaml` use JSON syntax, which is valid YAML 1.2, so runtime loading needs no additional YAML dependency. Metadata distinguishes calibrated values (BT-15 / JJ-10 / MS-12) from limits hardcoded in the validator.

## Config shape

```yaml
properties:
  title:
    required: true
    type: string
    max_length: 120
  phases:
    required: true
    type: array
    min_items: 2
    max_items: 8
    items:
      type: object
      properties:
        name:
          required: true
          type: string
          max_length: 28
        description:
          type: string
          max_length: 75
```

Supported rule keys:

| Key | Applies to | Purpose |
|-----|------------|---------|
| `required` | any | Field must be present and non-null |
| `type` | any | `string`, `array`, `object`, `integer`, `number`, `boolean` |
| `min_length` / `max_length` | string | Character limits (section 15) |
| `min_items` / `max_items` | array | Item count limits (section 15, 18.1) |
| `items.properties` | array of objects | Per-element field rules |
| `properties` | object | Nested object field rules |

## Registration (BT-15+)

```python
from services.validation.constraint_validator import LayoutConstraintRegistry

registry = LayoutConstraintRegistry()
registry.register("TIMELINE_01", timeline_config)
registry.validate_slide_spec(slide_spec)
```

AT-7 provides the engine; layout groups register configs when BT-15 / JJ-10 / MS-12 land.

Group A registration is additive and uses the same registry:

```python
from services.slides.group_a_constraints import register_group_a_constraints
from services.validation.constraint_validator import LayoutConstraintRegistry

registry = register_group_a_constraints(LayoutConstraintRegistry())
```

Group B registration is the same pattern:

```python
from services.slides.group_b_constraints import register_group_b_constraints
from services.validation.constraint_validator import LayoutConstraintRegistry

registry = register_group_b_constraints(LayoutConstraintRegistry())
```

Group C registration is additive on the same registry:

```python
from services.slides.group_c_constraints import register_group_c_constraints
from services.validation.constraint_validator import LayoutConstraintRegistry

registry = register_group_c_constraints(LayoutConstraintRegistry())
```
