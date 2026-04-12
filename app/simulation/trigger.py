
class DTrigger:
    def __init__(self) -> None:
        self._current = 0

    @property
    def current(self) -> int:
        return self._current

    def latch(self, value: int) -> None:
        self._current = value
