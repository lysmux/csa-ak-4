from app.simulation.mux import DSPMux, RSPMux


class Stack:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._mem: list[int] = [0] * capacity
        self._sp = 0

    @property
    def sp(self) -> int:
        return self._sp

    @sp.setter
    def sp(self, value: int) -> None:
        if value >= self.capacity:
            self._sp = self.capacity - 1
        elif value < 0:
            self._sp = 0
        else:
            self._sp = value

    def read(self) -> int:
        return self._mem[self._sp]

    def write(self, value: int) -> None:
        self._mem[self.sp] = value

    @property
    def stack(self) -> list[int]:
        return [self._mem[i] if i < self._sp else 0 for i in range(self.capacity)]


class DataStack(Stack):
    def __init__(self, capacity: int) -> None:
        super().__init__(capacity)

        self._tos = 0
        self._nos = 0

    @property
    def tos(self) -> int:
        return self._tos

    @tos.setter
    def tos(self, value: int) -> None:
        self._tos = value

    @property
    def nos(self) -> int:
        return self._nos

    @nos.setter
    def nos(self, value: int) -> None:
        self._nos = value

    @property
    def stack(self) -> list[int]:
        view = [0] * self.capacity
        for k in range(max(self._sp - 2, 0)):
            view[k] = self._mem[k + 2]
        if self._sp >= 2:
            view[self._sp - 2] = self._nos
        if self._sp >= 1:
            view[self._sp - 1] = self._tos
        return view

    def write_nos(self) -> None:
        self._mem[self._sp] = self._nos

    def latch_sp(self, mux: DSPMux) -> None:
        match mux:
            case DSPMux.INC:
                self.sp += 1
            case DSPMux.DEC:
                self.sp -= 1


class ReturnStack(Stack):
    def __init__(self, capacity: int) -> None:
        super().__init__(capacity)

    def latch_sp(self, mux: RSPMux) -> None:
        match mux:
            case RSPMux.INC:
                self.sp += 1
            case RSPMux.DEC:
                self.sp -= 1
