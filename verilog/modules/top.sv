import isa_pkg::*;

module top(
    input  wire clk,
    input  wire rst,

    output logic [7:0]  operand,
    output opcode_t     opcode,

    output logic [15:0] d_stack_tos,
    output logic [15:0] d_stack_nos,

    output logic [15:0] r_stack_tos,

    output logic        halt
);
    state_t     state, next_state;
    logic [2:0] step,  next_step;

    // ---------------- IR ----------------
    logic        ir_latch;
    logic [15:0] ir;

    // ---------------- PC ----------------
    logic [7:0]  pc;
    logic        pc_latch;
    pc_mux_t     pc_sel;
    pc_reg #(.ADDR_WIDTH(8)) u_pc (
        .clk(clk), .rst(rst),
        .latch(pc_latch), .sel(pc_sel),
        .ir_op(operand),
        .r_stack_tos(r_stack_tos[7:0]),
        .pc(pc)
    );

    // ---------------- Instruction memory ----------------
    logic        instr_ram_we;
    logic [15:0] instr_ram_wdata;
    logic [15:0] instr_ram_rdata;
    ram #(.ADDR_WIDTH(8), .DATA_WIDTH(16)) instr_ram (
        .clk(clk), .we(instr_ram_we),
        .addr(pc), .wdata(instr_ram_wdata),
        .rdata(instr_ram_rdata)
    );

    always_ff @(posedge clk) begin
        if (rst)           ir <= '0;
        else if (ir_latch) ir <= instr_ram_rdata;
    end
    assign opcode  = opcode_t'(ir[15:8]);
    assign operand = ir[7:0];

    // ---------------- AR ----------------
    logic [7:0]  ar;
    logic        ar_latch;
    ar_mux_t     ar_sel;
    ar_reg #(.ADDR_WIDTH(8)) u_ar (
        .clk(clk), .rst(rst),
        .latch(ar_latch), .sel(ar_sel),
        .ir_op(operand),
        .stack_tos(d_stack_tos[7:0]),
        .ar(ar)
    );

    // ---------------- Data memory ----------------
    logic        data_ram_we;
    logic [15:0] data_ram_wdata;
    logic [15:0] data_ram_rdata;
    ram #(.ADDR_WIDTH(8), .DATA_WIDTH(16)) data_ram (
        .clk(clk), .we(data_ram_we),
        .addr(ar), .wdata(data_ram_wdata),
        .rdata(data_ram_rdata)
    );

    // ---------------- ALU ----------------
    logic [15:0] alu_left, alu_right, alu_result;
    opcode_t     alu_op;
    logic        alu_n, alu_z, alu_v, alu_c;
    alu u_alu (
        .left(alu_left), .right(alu_right),
        .op(alu_op),
        .result(alu_result),
        .N(alu_n), .Z(alu_z), .V(alu_v), .C(alu_c)
    );

    // ---------------- Flags ----------------
    logic [3:0] flags;
    wire N = flags[0];
    wire Z = flags[1];
    wire V = flags[2];
    wire C = flags[3];
    logic flags_latch;
    always_ff @(posedge clk) begin
        if (rst)              flags <= '0;
        else if (flags_latch) flags <= {alu_c, alu_v, alu_z, alu_n};
    end

    // ---------------- Data stack ----------------
    stack_act_t  d_act;
    d_src_t      d_src;
    logic [15:0] d_wdata;
    stack u_d_stack (
        .clk(clk), .rst(rst),
        .act(d_act), .wdata(d_wdata),
        .tos(d_stack_tos), .nos(d_stack_nos)
    );
    always_comb begin
        unique case (d_src)
            D_SRC_IR:   d_wdata = {{8{1'b0}}, operand};
            D_SRC_ALU:  d_wdata = alu_result;
            D_SRC_MEM:  d_wdata = data_ram_rdata;
            D_SRC_TOS:  d_wdata = d_stack_tos;
            D_SRC_NOS:  d_wdata = d_stack_nos;
            D_SRC_RTOS: d_wdata = r_stack_tos;
            default:    d_wdata = '0;
        endcase
    end

    // ---------------- Return stack ----------------
    stack_act_t  r_act;
    r_src_t      r_src;
    logic [15:0] r_wdata;
    stack u_r_stack (
        .clk(clk), .rst(rst),
        .act(r_act), .wdata(r_wdata),
        .tos(r_stack_tos), .nos()
    );
    always_comb begin
        unique case (r_src)
            R_SRC_PC:  r_wdata = {{8{1'b0}}, pc};
            R_SRC_TOS: r_wdata = d_stack_tos;
            R_SRC_ALU: r_wdata = alu_result;
            default:   r_wdata = '0;
        endcase
    end

    // ---------------- State register ----------------
    always_ff @(posedge clk) begin
        if (rst) begin
            state <= ST_FETCH;
            step  <= '0;
        end else begin
            state <= next_state;
            step  <= next_step;
        end
    end

    // ---------------- Branch condition ----------------
    logic branch_taken;
    always_comb begin
        case (opcode)
            OP_JMP:  branch_taken = 1'b1;
            OP_JZ:   branch_taken = Z;
            OP_JNZ:  branch_taken = ~Z;
            OP_JPL:  branch_taken = ~N;
            OP_JMI:  branch_taken = N;
            OP_JGE:  branch_taken = (N == V);
            OP_JL:   branch_taken = (N != V);
            OP_JG:   branch_taken = ~Z & (N == V);
            OP_JLE:  branch_taken =  Z | (N != V);
            OP_JC:   branch_taken = C;
            OP_JNC:  branch_taken = ~C;
            OP_JV:   branch_taken = V;
            OP_JNV:  branch_taken = ~V;
            default: branch_taken = 1'b0;
        endcase
    end

    // ---------------- Control unit ----------------
    always_comb begin
        ir_latch        = 1'b0;
        pc_latch        = 1'b0; pc_sel = PC_MUX_NEXT;
        ar_latch        = 1'b0; ar_sel = AR_MUX_IR;
        d_act           = STACK_NONE; d_src = D_SRC_IR;
        r_act           = STACK_NONE; r_src = R_SRC_PC;
        flags_latch     = 1'b0;
        alu_op          = opcode;
        alu_left        = d_stack_nos;
        alu_right       = d_stack_tos;
        data_ram_we     = 1'b0;
        data_ram_wdata  = d_stack_tos;
        instr_ram_we    = 1'b0;
        instr_ram_wdata = '0;
        next_state      = state;
        next_step       = '0;
        halt            = 1'b0;

        case (state)
            ST_FETCH: begin
                ir_latch   = 1'b1;
                pc_latch   = 1'b1; pc_sel = PC_MUX_NEXT;
                next_state = ST_EXECUTE;
            end
            ST_EXECUTE: decode_execute();
            ST_HALT:    halt = 1'b1;
            default:    ;
        endcase
    end

    task automatic decode_execute();
        case (opcode)
            OP_HALT: next_state = ST_HALT;
            OP_NOP:  next_state = ST_FETCH;

            // ---- stack manipulation ----
            OP_PUSH: begin
                d_act = STACK_PUSH; d_src = D_SRC_IR;
                next_state = ST_FETCH;
            end
            OP_DUP: begin
                d_act = STACK_PUSH; d_src = D_SRC_TOS;
                next_state = ST_FETCH;
            end
            OP_DROP: begin
                d_act = STACK_POP;
                next_state = ST_FETCH;
            end
            OP_SWAP: begin
                d_act = STACK_SWAP;
                next_state = ST_FETCH;
            end
            OP_OVER: begin
                d_act = STACK_PUSH; d_src = D_SRC_NOS;
                next_state = ST_FETCH;
            end

            // ---- binary ALU ----
            OP_ADD, OP_SUB, OP_MUL, OP_DIV,
            OP_AND, OP_OR,  OP_XOR, OP_SHL, OP_SHR: begin
                alu_left    = d_stack_nos;
                alu_right   = d_stack_tos;
                alu_op      = opcode;
                d_act       = STACK_BINOP; d_src = D_SRC_ALU;
                flags_latch = 1'b1;
                next_state  = ST_FETCH;
            end

            // ---- unary ALU ----
            OP_INC, OP_DEC, OP_NEG, OP_NOT: begin
                alu_left    = d_stack_tos;
                alu_right   = '0;
                alu_op      = opcode;
                d_act       = STACK_REPLACE; d_src = D_SRC_ALU;
                flags_latch = 1'b1;
                next_state  = ST_FETCH;
            end

            // ---- CMP ----
            OP_CMP: begin
                alu_left    = d_stack_nos;
                alu_right   = d_stack_tos;
                alu_op      = OP_SUB;
                flags_latch = 1'b1;
                next_state  = ST_FETCH;
            end

            // ---- branches ----
            OP_JMP, OP_JZ, OP_JNZ, OP_JPL, OP_JMI,
            OP_JGE, OP_JL,  OP_JG,  OP_JLE,
            OP_JC,  OP_JNC, OP_JV,  OP_JNV: begin
                if (branch_taken) begin
                    pc_latch = 1'b1; pc_sel = PC_MUX_ADDRESS;
                end
                next_state = ST_FETCH;
            end

            // ---- subroutines ----
            OP_CALL: begin
                r_act    = STACK_PUSH; r_src = R_SRC_PC;
                pc_latch = 1'b1; pc_sel = PC_MUX_ADDRESS;
                next_state = ST_FETCH;
            end
            OP_RET: begin
                pc_latch = 1'b1; pc_sel = PC_MUX_R_STACK;
                r_act    = STACK_POP;
                next_state = ST_FETCH;
            end

            // ---- d-stack <-> r-stack ----
            OP_PSHR: begin
                r_act = STACK_PUSH; r_src = R_SRC_TOS;
                d_act = STACK_POP;
                next_state = ST_FETCH;
            end
            OP_POPR: begin
                d_act = STACK_PUSH; d_src = D_SRC_RTOS;
                r_act = STACK_POP;
                next_state = ST_FETCH;
            end

            // ---- LOOP ----
            OP_LOOP: begin
                alu_left    = r_stack_tos;
                alu_right   = '0;
                alu_op      = OP_DEC;
                flags_latch = 1'b1;
                if (alu_z) begin
                    r_act = STACK_POP;
                end else begin
                    r_act = STACK_REPLACE; r_src = R_SRC_ALU;
                    pc_latch = 1'b1; pc_sel = PC_MUX_ADDRESS;
                end
                next_state = ST_FETCH;
            end

            // ---- memory: direct addressing ----
            OP_LOAD: begin
                case (step)
                    3'd0: begin
                        ar_sel = AR_MUX_IR; ar_latch = 1'b1;
                        next_step  = 3'd1;
                        next_state = ST_EXECUTE;
                    end
                    default: begin
                        d_act = STACK_PUSH; d_src = D_SRC_MEM;
                        next_state = ST_FETCH;
                    end
                endcase
            end
            OP_STORE: begin
                case (step)
                    3'd0: begin
                        ar_sel = AR_MUX_IR; ar_latch = 1'b1;
                        next_step  = 3'd1;
                        next_state = ST_EXECUTE;
                    end
                    default: begin
                        data_ram_we    = 1'b1;
                        data_ram_wdata = d_stack_tos;
                        d_act          = STACK_POP;
                        next_state     = ST_FETCH;
                    end
                endcase
            end

            // ---- memory: indirect addressing ----
            OP_LOADI: begin
                case (step)
                    3'd0: begin
                        ar_sel = AR_MUX_TOS; ar_latch = 1'b1;
                        d_act  = STACK_POP;
                        next_step  = 3'd1;
                        next_state = ST_EXECUTE;
                    end
                    default: begin
                        d_act = STACK_PUSH; d_src = D_SRC_MEM;
                        next_state = ST_FETCH;
                    end
                endcase
            end
            OP_STOREI: begin
                case (step)
                    3'd0: begin
                        ar_sel = AR_MUX_TOS; ar_latch = 1'b1;
                        d_act  = STACK_POP;
                        next_step  = 3'd1;
                        next_state = ST_EXECUTE;
                    end
                    default: begin
                        data_ram_we    = 1'b1;
                        data_ram_wdata = d_stack_tos;
                        d_act          = STACK_POP;
                        next_state     = ST_FETCH;
                    end
                endcase
            end

            default: next_state = ST_FETCH;
        endcase
    endtask

endmodule
