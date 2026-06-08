`timescale 1ns/1ps

import isa_pkg::*;

module tb_top;
    logic clk = 1'b0;
    logic rst = 1'b1;

    logic [7:0]  operand;
    opcode_t     opcode;
    logic [15:0] d_stack_tos;
    logic [15:0] d_stack_nos;
    logic [15:0] r_stack_tos;
    logic        halt;

    top dut (
        .clk(clk),
        .rst(rst),
        .operand(operand),
        .opcode(opcode),
        .d_stack_tos(d_stack_tos),
        .d_stack_nos(d_stack_nos),
        .r_stack_tos(r_stack_tos),
        .halt(halt)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("tb_top.vcd");
        $dumpvars(0, tb_top);

        dut.instr_ram.mem[0] = 16'h1003;  // PUSH 3
        dut.instr_ram.mem[1] = 16'h1005;  // PUSH 5
        dut.instr_ram.mem[2] = 16'h3000;  // ADD
        dut.instr_ram.mem[3] = 16'h1001;  // PUSH
        dut.instr_ram.mem[4] = 16'h3100;  // SUB
        dut.instr_ram.mem[5] = 16'h0200;  // HALT

        rst = 1'b1;
        #20;
        rst = 1'b0;

        wait (halt);
        #10;

        $display("opcode=%h operand=%h tos=%0d nos=%0d halt=%b",
                 opcode, operand, d_stack_tos, d_stack_nos, halt);

        if (d_stack_tos === 16'd7)
            $display("PASS: 3 + 5 - 1 = %0d", d_stack_tos);
        else
            $display("FAIL: expected 7, got %0d", d_stack_tos);

        $finish;
    end

    initial begin
        #1000;
        $display("TIMEOUT (halt not reached)");
        $finish;
    end
endmodule
