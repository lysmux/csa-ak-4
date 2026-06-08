import isa_pkg::*;

module ar_reg
  #(parameter ADDR_WIDTH = 8)(
    input  wire clk,
    input  wire rst,

    input  wire     latch,
    input  ar_mux_t sel,

    input  wire [ADDR_WIDTH-1:0] ir_op,
    input  wire [ADDR_WIDTH-1:0] stack_tos,

    output logic [ADDR_WIDTH-1:0] ar
  );
  logic [ADDR_WIDTH-1:0] next_ar;

  always_comb begin
    unique case (sel)
      AR_MUX_IR:  next_ar = ir_op;
      AR_MUX_TOS: next_ar = stack_tos;
      default:    next_ar = '0;
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst)        ar <= '0;
    else if (latch) ar <= next_ar;
  end
endmodule
