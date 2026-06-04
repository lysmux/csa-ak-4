from app.simulation.mux import DSPMux


class Stack:
    """Register-model stack: TOS/NOS are registers, deeper cells live in memory.

    `sp` is the logical depth. The sequencing of spill/fill and the address
    arithmetic lives in the data path / control unit; this class only exposes
    the registers, the backing memory port, and `latch_sp` (+1 / -1).
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._mem: list[int] = [0] * capacity
        self.sp = 0

        self._tos = 0
        self._nos = 0

    def latch_sp(self, mux: DSPMux) -> None:
        if mux is DSPMux.INC:
            if self.sp >= self.capacity:
                msg = "Stack overflow"
                raise ValueError(msg)
            self.sp += 1
        else:
            if self.sp <= 0:
                msg = "Stack underflow"
                raise ValueError(msg)
            self.sp -= 1

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

    def read_mem(self, address: int) -> int:
        return self._mem[address]

    def write_mem(self, address: int, value: int) -> None:
        self._mem[address] = value

    @property
    def stack(self) -> list[int]:
        """Logical stack contents (bottom-to-top), padded to capacity with zeros."""
        view = [0] * self.capacity
        for i in range(max(self.sp - 2, 0)):
            view[i] = self._mem[i]
        if self.sp >= 2:
            view[self.sp - 2] = self._nos
        if self.sp >= 1:
            view[self.sp - 1] = self._tos
        return view
