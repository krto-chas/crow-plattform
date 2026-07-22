# CCM identity review

`same_as_candidate` is only a deterministic review candidate. It never merges objects.

A reviewer may resolve a candidate as:

- `same_as_confirmed`: the two observations are judged to refer to the same physical object.
- `not_same_as`: the observations are judged to refer to different physical objects.

The resolution preserves the candidate relation, both source observations, their evidence, reviewer,
rationale and timestamp. No automatic object merge or evidence deletion is performed.
