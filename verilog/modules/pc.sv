import isa_pkg::*;

module pc_reg
  #(parameter ADDR_WIDTH = 8)(
    input  wire clk,
    input  wire rst,

    input  wire     latch,
    input  pc_mux_t sel,

    input  wire [ADDR_WIDTH-1:0] ir_op,
    input  wire [ADDR_WIDTH-1:0] r_stack_tos,

    output logic [ADDR_WIDTH-1:0] pc
  );
  logic [ADDR_WIDTH-1:0] next_pc;

  always_comb begin
    unique case (sel)
      PC_MUX_NEXT:    next_pc = pc + 1'b1;
      PC_MUX_ADDRESS: next_pc = ir_op;
      PC_MUX_R_STACK: next_pc = r_stack_tos;
      default:        next_pc = '0;
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst)        pc <= '0;
    else if (latch) pc <= next_pc;
  end
endmodule
