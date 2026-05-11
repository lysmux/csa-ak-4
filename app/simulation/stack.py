class Stack:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.stack: list[int] = [0 for _ in range(capacity)]
        self.sp = -1

    def push(self, value: int) -> None:
        if self.sp >= self.capacity:
            msg = "Stack overflow"
            raise ValueError(msg)

        self.sp += 1
        self.stack[self.sp] = value

    def pop(self) -> int:
        if self.sp < 0:
            msg = "Stack underflow"
            raise ValueError(msg)

        value = self.stack[self.sp]
        self.stack[self.sp] = 0
        self.sp -= 1

        return value

    @property
    def tos(self) -> int:
        return self.stack[self.sp]

    @property
    def nos(self) -> int:
        return self.stack[self.sp - 1]
