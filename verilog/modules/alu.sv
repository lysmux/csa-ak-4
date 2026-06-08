import isa_pkg::*;

module alu(
    input  wire [15:0] left,
    input  wire [15:0] right,
    input  opcode_t    op,

    output logic [15:0] result,
    output logic        N,
    output logic        Z,
    output logic        V,
    output logic        C
);
  always_comb begin
    N      = 1'b0;
    Z      = 1'b0;
    V      = 1'b0;
    C      = 1'b0;
    result = 16'd0;

    case (op)
      OP_ADD: begin
        {C, result} = {1'b0, left} + {1'b0, right};
        V = (~(left[15] ^ right[15])) & (result[15] ^ left[15]);
      end
      OP_SUB: begin
        {C, result} = {1'b0, left} - {1'b0, right};
        C = ~C;
        V = (left[15] ^ right[15]) & (result[15] ^ left[15]);
      end
      OP_MUL: result = left * right;
      OP_DIV: result = (right != 16'd0) ? (left / right) : 16'd0;
      OP_INC: {C, result} = {1'b0, left} + 17'd1;
      OP_DEC: begin
        {C, result} = {1'b0, left} - 17'd1;
        C = ~C;
      end
      OP_NEG: result = -left;
      OP_NOT: result = ~left;
      OP_AND: result = left & right;
      OP_OR:  result = left | right;
      OP_XOR: result = left ^ right;
      OP_SHL: result = left << right[3:0];
      OP_SHR: result = left >> right[3:0];
      default: result = 16'd0;
    endcase

    Z = (result == 16'b0);
    N = result[15];
  end
endmodule
