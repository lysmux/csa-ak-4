import isa_pkg::*;

module stack
  #(
    parameter WIDTH     = 16,
    parameter DEPTH     = 16,
    parameter PTR_WIDTH = 4
  )(
    input  wire              clk,
    input  wire              rst,
    input  stack_act_t       act,
    input  wire [WIDTH-1:0]  wdata,
    output logic [WIDTH-1:0] tos,
    output logic [WIDTH-1:0] nos
  );
  logic [WIDTH-1:0]     mem [DEPTH];
  logic [PTR_WIDTH-1:0] sp;

  assign tos = (sp >= 1) ? mem[sp - 1'b1] : '0;
  assign nos = (sp >= 2) ? mem[sp - 2'd2] : '0;

  always_ff @(posedge clk) begin
    if (rst) begin
      sp <= '0;
    end else begin
      unique case (act)
        STACK_PUSH: begin
          mem[sp] <= wdata;
          sp <= sp + 1'b1;
        end
        STACK_POP: begin
          sp <= sp - 1'b1;
        end
        STACK_REPLACE: begin
          mem[sp - 1'b1] <= wdata;
        end
        STACK_BINOP: begin
          mem[sp - 2'd2] <= wdata;
          sp <= sp - 1'b1;
        end
        STACK_SWAP: begin
          mem[sp - 1'b1] <= nos;
          mem[sp - 2'd2] <= tos;
        end
        STACK_NONE: ;
        default:    ;
      endcase
    end
  end
endmodule
