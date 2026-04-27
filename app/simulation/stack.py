from app.simulation.register import Register


class Stack:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.stack: list[int] = [0 for _ in range(capacity)]
        self.sp = -1

        self.tos = Register()
        self.nos = Register()

        self.v_tos = False
        self.v_nos = False

    def push(self, value: int) -> None:
        if self.sp >= self.capacity:
            msg = "Stack overflow"
            raise ValueError(msg)

        if self.v_tos and self.v_nos:
            self.sp += 1
            self.stack[self.sp] = self.nos.current

        if self.v_tos:
            self.nos.latch(self.tos.current)
            self.v_nos = True

        self.tos.latch(value)
        self.v_tos = True

    def pop(self) -> int:
        if not self.v_tos:
            msg = "Stack underflow"
            raise ValueError(msg)

        result = self.tos.current

        if self.v_nos:
            self.tos.latch(self.nos.current)
        else:
            self.tos.latch(0)
            self.v_tos = False

        if self.sp >= 0:
            self.nos.latch(self.stack[self.sp])
            self.stack[self.sp] = 0
            self.sp -= 1
        else:
            self.nos.latch(0)
            self.v_nos = False

        return result
