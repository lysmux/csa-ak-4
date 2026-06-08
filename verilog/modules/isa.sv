package isa_pkg;

  typedef enum logic [7:0] {
    OP_NOP    = 8'h01,
    OP_HALT   = 8'h02,

    // Stack
    OP_PUSH   = 8'h10,
    OP_DUP    = 8'h11,
    OP_DROP   = 8'h12,
    OP_SWAP   = 8'h13,
    OP_OVER   = 8'h14,

    // Memory
    OP_LOAD   = 8'h20,
    OP_STORE  = 8'h21,
    OP_LOADI  = 8'h22,
    OP_STOREI = 8'h23,

    // Arithmetic
    OP_ADD    = 8'h30,
    OP_SUB    = 8'h31,
    OP_MUL    = 8'h32,
    OP_DIV    = 8'h33,
    OP_CMP    = 8'h34,
    OP_INC    = 8'h35,
    OP_DEC    = 8'h36,
    OP_NEG    = 8'h37,

    // Logic
    OP_AND    = 8'h40,
    OP_OR     = 8'h41,
    OP_XOR    = 8'h42,
    OP_NOT    = 8'h43,
    OP_SHL    = 8'h44,
    OP_SHR    = 8'h45,

    // Conditional jumps
    OP_JZ     = 8'h50,
    OP_JNZ    = 8'h51,
    OP_JPL    = 8'h52,
    OP_JMI    = 8'h53,
    OP_JGE    = 8'h54,
    OP_JL     = 8'h55,
    OP_JG     = 8'h56,
    OP_JLE    = 8'h57,
    OP_JC     = 8'h58,
    OP_JNC    = 8'h59,
    OP_JV     = 8'h5A,
    OP_JNV    = 8'h5B,

    // Control flow
    OP_JMP    = 8'h60,
    OP_CALL   = 8'h61,
    OP_RET    = 8'h62,
    OP_LOOP   = 8'h63,
    OP_PSHR   = 8'h64,
    OP_POPR   = 8'h65,

    // Interrupts
    OP_EI     = 8'h70,
    OP_DI     = 8'h71,
    OP_RTI    = 8'h72
  } opcode_t;

  typedef enum logic [1:0] {
    PC_MUX_NEXT    = 2'd0,
    PC_MUX_ADDRESS = 2'd1,
    PC_MUX_R_STACK = 2'd2
  } pc_mux_t;

  typedef enum logic {
    AR_MUX_IR  = 1'd0,
    AR_MUX_TOS = 1'd1
  } ar_mux_t;

  // Data-stack write source (mux feeding the stack data input).
  typedef enum logic [2:0] {
    D_SRC_IR   = 3'd0,
    D_SRC_ALU  = 3'd1,
    D_SRC_MEM  = 3'd2,
    D_SRC_TOS  = 3'd3,
    D_SRC_NOS  = 3'd4,
    D_SRC_RTOS = 3'd5
  } d_src_t;

  // Return-stack write source.
  typedef enum logic [1:0] {
    R_SRC_PC  = 2'd0,
    R_SRC_TOS = 2'd1,
    R_SRC_ALU = 2'd2
  } r_src_t;

  // Stack mutation, shared by the data and return stacks.
  // The return stack only uses NONE/PUSH/POP/REPLACE.
  typedef enum logic [2:0] {
    STACK_NONE    = 3'd0,
    STACK_PUSH    = 3'd1,
    STACK_POP     = 3'd2,
    STACK_REPLACE = 3'd3,
    STACK_BINOP   = 3'd4,
    STACK_SWAP    = 3'd5
  } stack_act_t;

  typedef enum logic [1:0] {
    ST_FETCH   = 2'd0,
    ST_EXECUTE = 2'd1,
    ST_HALT    = 2'd2
  } state_t;

endpackage
