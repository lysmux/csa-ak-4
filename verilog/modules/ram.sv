module ram
  #(
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 16
  )(
    input  wire                   clk,
    input  wire                   we,

    input  wire [ADDR_WIDTH-1:0]  addr,
    input  wire [DATA_WIDTH-1:0]  wdata,
    output logic [DATA_WIDTH-1:0] rdata
  );
  logic [DATA_WIDTH-1:0] mem [(1 << ADDR_WIDTH)-1:0];

  assign rdata = mem[addr];

  always_ff @(posedge clk) begin
    if (we) mem[addr] <= wdata;
  end
endmodule
