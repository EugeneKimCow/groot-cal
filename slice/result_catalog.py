"""대화·API가 materialized result를 명시적 reference로 해소하는 catalog."""


class ResultCatalog:
    def __init__(self):
        self._results = {}
        self._aliases = {}
        self._latest = None

    def add(self, stored, aliases=None):
        result_id = stored["result_id"]
        existing = self._results.get(result_id)
        if existing is not None and existing != stored:
            raise ValueError(f"result_id collision: {result_id}")
        self._results[result_id] = stored
        self._latest = result_id
        for alias in aliases or []:
            self._aliases[alias] = result_id
        return result_id

    def resolve(self, reference="latest"):
        if reference == "latest":
            result_id = self._latest
        else:
            result_id = self._aliases.get(reference, reference)
        return None if result_id is None else self._results.get(result_id)

    def ids(self):
        return sorted(self._results)
