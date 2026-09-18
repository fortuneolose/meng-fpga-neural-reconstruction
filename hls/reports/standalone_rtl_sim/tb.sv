`timescale 1ns/1ps
module tb;
parameter    ap_ST_fsm_state1 = 13'd1;
parameter    ap_ST_fsm_state2 = 13'd2;
parameter    ap_ST_fsm_state3 = 13'd4;
parameter    ap_ST_fsm_state4 = 13'd8;
parameter    ap_ST_fsm_state5 = 13'd16;
parameter    ap_ST_fsm_state6 = 13'd32;
parameter    ap_ST_fsm_state7 = 13'd64;
parameter    ap_ST_fsm_state8 = 13'd128;
parameter    ap_ST_fsm_state9 = 13'd256;
parameter    ap_ST_fsm_state10 = 13'd512;
parameter    ap_ST_fsm_state11 = 13'd1024;
parameter    ap_ST_fsm_state12 = 13'd2048;
parameter    ap_ST_fsm_state13 = 13'd4096;
parameter    C_S_AXI_CONTROL_DATA_WIDTH = 32;
parameter    C_S_AXI_CONTROL_ADDR_WIDTH = 6;
parameter    C_S_AXI_DATA_WIDTH = 32;
parameter    C_M_AXI_GMEM0_ID_WIDTH = 1;
parameter    C_M_AXI_GMEM0_ADDR_WIDTH = 64;
parameter    C_M_AXI_GMEM0_DATA_WIDTH = 32;
parameter    C_M_AXI_GMEM0_AWUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM0_ARUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM0_WUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM0_RUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM0_BUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM0_USER_VALUE = 0;
parameter    C_M_AXI_GMEM0_PROT_VALUE = 0;
parameter    C_M_AXI_GMEM0_CACHE_VALUE = 3;
parameter    C_M_AXI_DATA_WIDTH = 32;
parameter    C_M_AXI_GMEM1_ID_WIDTH = 1;
parameter    C_M_AXI_GMEM1_ADDR_WIDTH = 64;
parameter    C_M_AXI_GMEM1_DATA_WIDTH = 32;
parameter    C_M_AXI_GMEM1_AWUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM1_ARUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM1_WUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM1_RUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM1_BUSER_WIDTH = 1;
parameter    C_M_AXI_GMEM1_USER_VALUE = 0;
parameter    C_M_AXI_GMEM1_PROT_VALUE = 0;
parameter    C_M_AXI_GMEM1_CACHE_VALUE = 3;
parameter C_S_AXI_CONTROL_WSTRB_WIDTH = (32 / 8);
parameter C_S_AXI_WSTRB_WIDTH = (32 / 8);
parameter C_M_AXI_GMEM0_WSTRB_WIDTH = (32 / 8);
parameter C_M_AXI_WSTRB_WIDTH = (32 / 8);
parameter C_M_AXI_GMEM1_WSTRB_WIDTH = (32 / 8);
reg  ap_clk;
reg  ap_rst_n;
wire  m_axi_gmem0_AWVALID;
wire  m_axi_gmem0_AWREADY;
wire [C_M_AXI_GMEM0_ADDR_WIDTH - 1:0] m_axi_gmem0_AWADDR;
wire [C_M_AXI_GMEM0_ID_WIDTH - 1:0] m_axi_gmem0_AWID;
wire [7:0] m_axi_gmem0_AWLEN;
wire [2:0] m_axi_gmem0_AWSIZE;
wire [1:0] m_axi_gmem0_AWBURST;
wire [1:0] m_axi_gmem0_AWLOCK;
wire [3:0] m_axi_gmem0_AWCACHE;
wire [2:0] m_axi_gmem0_AWPROT;
wire [3:0] m_axi_gmem0_AWQOS;
wire [3:0] m_axi_gmem0_AWREGION;
wire [C_M_AXI_GMEM0_AWUSER_WIDTH - 1:0] m_axi_gmem0_AWUSER;
wire  m_axi_gmem0_WVALID;
wire  m_axi_gmem0_WREADY;
wire [C_M_AXI_GMEM0_DATA_WIDTH - 1:0] m_axi_gmem0_WDATA;
wire [C_M_AXI_GMEM0_WSTRB_WIDTH - 1:0] m_axi_gmem0_WSTRB;
wire  m_axi_gmem0_WLAST;
wire [C_M_AXI_GMEM0_ID_WIDTH - 1:0] m_axi_gmem0_WID;
wire [C_M_AXI_GMEM0_WUSER_WIDTH - 1:0] m_axi_gmem0_WUSER;
wire  m_axi_gmem0_ARVALID;
wire  m_axi_gmem0_ARREADY;
wire [C_M_AXI_GMEM0_ADDR_WIDTH - 1:0] m_axi_gmem0_ARADDR;
wire [C_M_AXI_GMEM0_ID_WIDTH - 1:0] m_axi_gmem0_ARID;
wire [7:0] m_axi_gmem0_ARLEN;
wire [2:0] m_axi_gmem0_ARSIZE;
wire [1:0] m_axi_gmem0_ARBURST;
wire [1:0] m_axi_gmem0_ARLOCK;
wire [3:0] m_axi_gmem0_ARCACHE;
wire [2:0] m_axi_gmem0_ARPROT;
wire [3:0] m_axi_gmem0_ARQOS;
wire [3:0] m_axi_gmem0_ARREGION;
wire [C_M_AXI_GMEM0_ARUSER_WIDTH - 1:0] m_axi_gmem0_ARUSER;
wire  m_axi_gmem0_RVALID;
wire  m_axi_gmem0_RREADY;
wire [C_M_AXI_GMEM0_DATA_WIDTH - 1:0] m_axi_gmem0_RDATA;
wire  m_axi_gmem0_RLAST;
wire [C_M_AXI_GMEM0_ID_WIDTH - 1:0] m_axi_gmem0_RID;
wire [C_M_AXI_GMEM0_RUSER_WIDTH - 1:0] m_axi_gmem0_RUSER;
wire [1:0] m_axi_gmem0_RRESP;
wire  m_axi_gmem0_BVALID;
wire  m_axi_gmem0_BREADY;
wire [1:0] m_axi_gmem0_BRESP;
wire [C_M_AXI_GMEM0_ID_WIDTH - 1:0] m_axi_gmem0_BID;
wire [C_M_AXI_GMEM0_BUSER_WIDTH - 1:0] m_axi_gmem0_BUSER;
wire  m_axi_gmem1_AWVALID;
wire  m_axi_gmem1_AWREADY;
wire [C_M_AXI_GMEM1_ADDR_WIDTH - 1:0] m_axi_gmem1_AWADDR;
wire [C_M_AXI_GMEM1_ID_WIDTH - 1:0] m_axi_gmem1_AWID;
wire [7:0] m_axi_gmem1_AWLEN;
wire [2:0] m_axi_gmem1_AWSIZE;
wire [1:0] m_axi_gmem1_AWBURST;
wire [1:0] m_axi_gmem1_AWLOCK;
wire [3:0] m_axi_gmem1_AWCACHE;
wire [2:0] m_axi_gmem1_AWPROT;
wire [3:0] m_axi_gmem1_AWQOS;
wire [3:0] m_axi_gmem1_AWREGION;
wire [C_M_AXI_GMEM1_AWUSER_WIDTH - 1:0] m_axi_gmem1_AWUSER;
wire  m_axi_gmem1_WVALID;
wire  m_axi_gmem1_WREADY;
wire [C_M_AXI_GMEM1_DATA_WIDTH - 1:0] m_axi_gmem1_WDATA;
wire [C_M_AXI_GMEM1_WSTRB_WIDTH - 1:0] m_axi_gmem1_WSTRB;
wire  m_axi_gmem1_WLAST;
wire [C_M_AXI_GMEM1_ID_WIDTH - 1:0] m_axi_gmem1_WID;
wire [C_M_AXI_GMEM1_WUSER_WIDTH - 1:0] m_axi_gmem1_WUSER;
wire  m_axi_gmem1_ARVALID;
wire  m_axi_gmem1_ARREADY;
wire [C_M_AXI_GMEM1_ADDR_WIDTH - 1:0] m_axi_gmem1_ARADDR;
wire [C_M_AXI_GMEM1_ID_WIDTH - 1:0] m_axi_gmem1_ARID;
wire [7:0] m_axi_gmem1_ARLEN;
wire [2:0] m_axi_gmem1_ARSIZE;
wire [1:0] m_axi_gmem1_ARBURST;
wire [1:0] m_axi_gmem1_ARLOCK;
wire [3:0] m_axi_gmem1_ARCACHE;
wire [2:0] m_axi_gmem1_ARPROT;
wire [3:0] m_axi_gmem1_ARQOS;
wire [3:0] m_axi_gmem1_ARREGION;
wire [C_M_AXI_GMEM1_ARUSER_WIDTH - 1:0] m_axi_gmem1_ARUSER;
wire  m_axi_gmem1_RVALID;
wire  m_axi_gmem1_RREADY;
wire [C_M_AXI_GMEM1_DATA_WIDTH - 1:0] m_axi_gmem1_RDATA;
wire  m_axi_gmem1_RLAST;
wire [C_M_AXI_GMEM1_ID_WIDTH - 1:0] m_axi_gmem1_RID;
wire [C_M_AXI_GMEM1_RUSER_WIDTH - 1:0] m_axi_gmem1_RUSER;
wire [1:0] m_axi_gmem1_RRESP;
wire  m_axi_gmem1_BVALID;
wire  m_axi_gmem1_BREADY;
wire [1:0] m_axi_gmem1_BRESP;
wire [C_M_AXI_GMEM1_ID_WIDTH - 1:0] m_axi_gmem1_BID;
wire [C_M_AXI_GMEM1_BUSER_WIDTH - 1:0] m_axi_gmem1_BUSER;
reg  s_axi_control_AWVALID;
wire  s_axi_control_AWREADY;
reg [C_S_AXI_CONTROL_ADDR_WIDTH - 1:0] s_axi_control_AWADDR;
reg  s_axi_control_WVALID;
wire  s_axi_control_WREADY;
reg [C_S_AXI_CONTROL_DATA_WIDTH - 1:0] s_axi_control_WDATA;
reg [C_S_AXI_CONTROL_WSTRB_WIDTH - 1:0] s_axi_control_WSTRB;
reg  s_axi_control_ARVALID;
wire  s_axi_control_ARREADY;
reg [C_S_AXI_CONTROL_ADDR_WIDTH - 1:0] s_axi_control_ARADDR;
wire  s_axi_control_RVALID;
reg  s_axi_control_RREADY;
wire [C_S_AXI_CONTROL_DATA_WIDTH - 1:0] s_axi_control_RDATA;
wire [1:0] s_axi_control_RRESP;
wire  s_axi_control_BVALID;
reg  s_axi_control_BREADY;
wire [1:0] s_axi_control_BRESP;
wire  interrupt;
reconstruction_accel dut (
    .ap_clk(ap_clk),
    .ap_rst_n(ap_rst_n),
    .m_axi_gmem0_AWVALID(m_axi_gmem0_AWVALID),
    .m_axi_gmem0_AWREADY(m_axi_gmem0_AWREADY),
    .m_axi_gmem0_AWADDR(m_axi_gmem0_AWADDR),
    .m_axi_gmem0_AWID(m_axi_gmem0_AWID),
    .m_axi_gmem0_AWLEN(m_axi_gmem0_AWLEN),
    .m_axi_gmem0_AWSIZE(m_axi_gmem0_AWSIZE),
    .m_axi_gmem0_AWBURST(m_axi_gmem0_AWBURST),
    .m_axi_gmem0_AWLOCK(m_axi_gmem0_AWLOCK),
    .m_axi_gmem0_AWCACHE(m_axi_gmem0_AWCACHE),
    .m_axi_gmem0_AWPROT(m_axi_gmem0_AWPROT),
    .m_axi_gmem0_AWQOS(m_axi_gmem0_AWQOS),
    .m_axi_gmem0_AWREGION(m_axi_gmem0_AWREGION),
    .m_axi_gmem0_AWUSER(m_axi_gmem0_AWUSER),
    .m_axi_gmem0_WVALID(m_axi_gmem0_WVALID),
    .m_axi_gmem0_WREADY(m_axi_gmem0_WREADY),
    .m_axi_gmem0_WDATA(m_axi_gmem0_WDATA),
    .m_axi_gmem0_WSTRB(m_axi_gmem0_WSTRB),
    .m_axi_gmem0_WLAST(m_axi_gmem0_WLAST),
    .m_axi_gmem0_WID(m_axi_gmem0_WID),
    .m_axi_gmem0_WUSER(m_axi_gmem0_WUSER),
    .m_axi_gmem0_ARVALID(m_axi_gmem0_ARVALID),
    .m_axi_gmem0_ARREADY(m_axi_gmem0_ARREADY),
    .m_axi_gmem0_ARADDR(m_axi_gmem0_ARADDR),
    .m_axi_gmem0_ARID(m_axi_gmem0_ARID),
    .m_axi_gmem0_ARLEN(m_axi_gmem0_ARLEN),
    .m_axi_gmem0_ARSIZE(m_axi_gmem0_ARSIZE),
    .m_axi_gmem0_ARBURST(m_axi_gmem0_ARBURST),
    .m_axi_gmem0_ARLOCK(m_axi_gmem0_ARLOCK),
    .m_axi_gmem0_ARCACHE(m_axi_gmem0_ARCACHE),
    .m_axi_gmem0_ARPROT(m_axi_gmem0_ARPROT),
    .m_axi_gmem0_ARQOS(m_axi_gmem0_ARQOS),
    .m_axi_gmem0_ARREGION(m_axi_gmem0_ARREGION),
    .m_axi_gmem0_ARUSER(m_axi_gmem0_ARUSER),
    .m_axi_gmem0_RVALID(m_axi_gmem0_RVALID),
    .m_axi_gmem0_RREADY(m_axi_gmem0_RREADY),
    .m_axi_gmem0_RDATA(m_axi_gmem0_RDATA),
    .m_axi_gmem0_RLAST(m_axi_gmem0_RLAST),
    .m_axi_gmem0_RID(m_axi_gmem0_RID),
    .m_axi_gmem0_RUSER(m_axi_gmem0_RUSER),
    .m_axi_gmem0_RRESP(m_axi_gmem0_RRESP),
    .m_axi_gmem0_BVALID(m_axi_gmem0_BVALID),
    .m_axi_gmem0_BREADY(m_axi_gmem0_BREADY),
    .m_axi_gmem0_BRESP(m_axi_gmem0_BRESP),
    .m_axi_gmem0_BID(m_axi_gmem0_BID),
    .m_axi_gmem0_BUSER(m_axi_gmem0_BUSER),
    .m_axi_gmem1_AWVALID(m_axi_gmem1_AWVALID),
    .m_axi_gmem1_AWREADY(m_axi_gmem1_AWREADY),
    .m_axi_gmem1_AWADDR(m_axi_gmem1_AWADDR),
    .m_axi_gmem1_AWID(m_axi_gmem1_AWID),
    .m_axi_gmem1_AWLEN(m_axi_gmem1_AWLEN),
    .m_axi_gmem1_AWSIZE(m_axi_gmem1_AWSIZE),
    .m_axi_gmem1_AWBURST(m_axi_gmem1_AWBURST),
    .m_axi_gmem1_AWLOCK(m_axi_gmem1_AWLOCK),
    .m_axi_gmem1_AWCACHE(m_axi_gmem1_AWCACHE),
    .m_axi_gmem1_AWPROT(m_axi_gmem1_AWPROT),
    .m_axi_gmem1_AWQOS(m_axi_gmem1_AWQOS),
    .m_axi_gmem1_AWREGION(m_axi_gmem1_AWREGION),
    .m_axi_gmem1_AWUSER(m_axi_gmem1_AWUSER),
    .m_axi_gmem1_WVALID(m_axi_gmem1_WVALID),
    .m_axi_gmem1_WREADY(m_axi_gmem1_WREADY),
    .m_axi_gmem1_WDATA(m_axi_gmem1_WDATA),
    .m_axi_gmem1_WSTRB(m_axi_gmem1_WSTRB),
    .m_axi_gmem1_WLAST(m_axi_gmem1_WLAST),
    .m_axi_gmem1_WID(m_axi_gmem1_WID),
    .m_axi_gmem1_WUSER(m_axi_gmem1_WUSER),
    .m_axi_gmem1_ARVALID(m_axi_gmem1_ARVALID),
    .m_axi_gmem1_ARREADY(m_axi_gmem1_ARREADY),
    .m_axi_gmem1_ARADDR(m_axi_gmem1_ARADDR),
    .m_axi_gmem1_ARID(m_axi_gmem1_ARID),
    .m_axi_gmem1_ARLEN(m_axi_gmem1_ARLEN),
    .m_axi_gmem1_ARSIZE(m_axi_gmem1_ARSIZE),
    .m_axi_gmem1_ARBURST(m_axi_gmem1_ARBURST),
    .m_axi_gmem1_ARLOCK(m_axi_gmem1_ARLOCK),
    .m_axi_gmem1_ARCACHE(m_axi_gmem1_ARCACHE),
    .m_axi_gmem1_ARPROT(m_axi_gmem1_ARPROT),
    .m_axi_gmem1_ARQOS(m_axi_gmem1_ARQOS),
    .m_axi_gmem1_ARREGION(m_axi_gmem1_ARREGION),
    .m_axi_gmem1_ARUSER(m_axi_gmem1_ARUSER),
    .m_axi_gmem1_RVALID(m_axi_gmem1_RVALID),
    .m_axi_gmem1_RREADY(m_axi_gmem1_RREADY),
    .m_axi_gmem1_RDATA(m_axi_gmem1_RDATA),
    .m_axi_gmem1_RLAST(m_axi_gmem1_RLAST),
    .m_axi_gmem1_RID(m_axi_gmem1_RID),
    .m_axi_gmem1_RUSER(m_axi_gmem1_RUSER),
    .m_axi_gmem1_RRESP(m_axi_gmem1_RRESP),
    .m_axi_gmem1_BVALID(m_axi_gmem1_BVALID),
    .m_axi_gmem1_BREADY(m_axi_gmem1_BREADY),
    .m_axi_gmem1_BRESP(m_axi_gmem1_BRESP),
    .m_axi_gmem1_BID(m_axi_gmem1_BID),
    .m_axi_gmem1_BUSER(m_axi_gmem1_BUSER),
    .s_axi_control_AWVALID(s_axi_control_AWVALID),
    .s_axi_control_AWREADY(s_axi_control_AWREADY),
    .s_axi_control_AWADDR(s_axi_control_AWADDR),
    .s_axi_control_WVALID(s_axi_control_WVALID),
    .s_axi_control_WREADY(s_axi_control_WREADY),
    .s_axi_control_WDATA(s_axi_control_WDATA),
    .s_axi_control_WSTRB(s_axi_control_WSTRB),
    .s_axi_control_ARVALID(s_axi_control_ARVALID),
    .s_axi_control_ARREADY(s_axi_control_ARREADY),
    .s_axi_control_ARADDR(s_axi_control_ARADDR),
    .s_axi_control_RVALID(s_axi_control_RVALID),
    .s_axi_control_RREADY(s_axi_control_RREADY),
    .s_axi_control_RDATA(s_axi_control_RDATA),
    .s_axi_control_RRESP(s_axi_control_RRESP),
    .s_axi_control_BVALID(s_axi_control_BVALID),
    .s_axi_control_BREADY(s_axi_control_BREADY),
    .s_axi_control_BRESP(s_axi_control_BRESP),
    .interrupt(interrupt)
);
localparam [63:0] IN_BASE=64'h0000000110000000;
localparam [63:0] OUT_BASE=64'h0000000220000000;
localparam IN_MEM=32768, OUT_MEM=135168;
reg stall_enable=0;
integer cycle=0, frame=0, nframes=3, stress=0;
integer i,j,offset_in,offset_out,mismatches,case_start,rd_before,wr_before,fd;
reg [15:0] expected[0:65535];
reg [15:0] actual;
reg [31:0] status_word;
reg [63:0] input_address,output_address;
string case_id, output_file;
always #2.5 ap_clk=~ap_clk;
always @(posedge ap_clk) begin
    cycle<=cycle+1;
    if(cycle%1000000==0) $display("PROGRESS cycle=%0d frame=%0d",cycle,frame);
    if(cycle>100000000) $fatal(1,"Global timeout");
end

task axil_write(input [5:0] addr,input [31:0] data);
integer timeout;
begin
    @(negedge ap_clk);
    s_axi_control_AWADDR=addr; s_axi_control_AWVALID=1;
    timeout=0;
    do begin @(posedge ap_clk); timeout=timeout+1;
        if(timeout>100) $fatal(1,"AXI-Lite AW timeout");
    end while(s_axi_control_AWREADY !== 1'b1);
    @(negedge ap_clk); s_axi_control_AWVALID=0;
    if(stall_enable) repeat(2) @(negedge ap_clk);
    s_axi_control_WDATA=data; s_axi_control_WSTRB=4'hf; s_axi_control_WVALID=1;
    timeout=0;
    do begin @(posedge ap_clk); timeout=timeout+1;
        if(timeout>100) $fatal(1,"AXI-Lite W timeout");
    end while(s_axi_control_WREADY !== 1'b1);
    @(negedge ap_clk); s_axi_control_WVALID=0;
    if(stall_enable) repeat(3) @(negedge ap_clk);
    s_axi_control_BREADY=1; timeout=0;
    do begin @(posedge ap_clk); timeout=timeout+1;
        if(timeout>100) $fatal(1,"AXI-Lite B timeout");
    end while(s_axi_control_BVALID !== 1'b1);
    if(s_axi_control_BRESP !== 0) $fatal(1,"AXI-Lite write error");
    @(negedge ap_clk); s_axi_control_BREADY=0;
end
endtask

task axil_read(input [5:0] addr,output [31:0] data);
integer timeout;
begin
    @(negedge ap_clk); s_axi_control_ARADDR=addr; s_axi_control_ARVALID=1;
    timeout=0;
    do begin @(posedge ap_clk); timeout=timeout+1;
        if(timeout>100) $fatal(1,"AXI-Lite AR timeout");
    end while(s_axi_control_ARREADY !== 1'b1);
    @(negedge ap_clk); s_axi_control_ARVALID=0;
    if(stall_enable) repeat(3) @(negedge ap_clk);
    s_axi_control_RREADY=1; timeout=0;
    do begin @(posedge ap_clk); timeout=timeout+1;
        if(timeout>100) $fatal(1,"AXI-Lite R timeout");
    end while(s_axi_control_RVALID !== 1'b1);
    if(s_axi_control_RRESP !== 0 || ^s_axi_control_RDATA === 1'bx)
        $fatal(1,"AXI-Lite read error or unknown data");
    data=s_axi_control_RDATA;
    @(negedge ap_clk); s_axi_control_RREADY=0;
end
endtask

initial begin
    ap_clk=0; ap_rst_n=0;
    s_axi_control_AWVALID=0; s_axi_control_AWADDR=0;
    s_axi_control_WVALID=0; s_axi_control_WDATA=0; s_axi_control_WSTRB=0;
    s_axi_control_ARVALID=0; s_axi_control_ARADDR=0;
    s_axi_control_RREADY=0; s_axi_control_BREADY=0;
    if($value$plusargs("STALL=%d",stress)) stall_enable=(stress!=0);
    if($value$plusargs("CASES=%d",nframes)) begin end
    if(nframes<1 || nframes>3) $fatal(1,"CASES must be 1..3");
    repeat(20) @(negedge ap_clk);
    ap_rst_n=1;
    repeat(20) @(negedge ap_clk);
    for(frame=0;frame<nframes;frame=frame+1) begin
        case(frame) 0:case_id="0805"; 1:case_id="0809"; 2:case_id="0824"; endcase
        offset_in=256+frame*260; offset_out=256+frame*516;
        for(i=0;i<IN_MEM;i=i+1) begin input_ram.mem[i]=8'ha5; input_ram.written[i]=0; end
        for(i=0;i<OUT_MEM;i=i+1) begin output_ram.mem[i]=8'ha5; output_ram.written[i]=0; end
        $readmemh({case_id,"_input.hex"},input_ram.mem,offset_in,offset_in+16383);
        $readmemh({case_id,"_expected.hex"},expected);
        input_address=IN_BASE+offset_in; output_address=OUT_BASE+offset_out;
        input_ram.active_min=input_address; input_ram.active_max=input_address+16384;
        output_ram.active_min=output_address; output_ram.active_max=output_address+131072;
        axil_read(0,status_word);
        if(status_word[2] !== 1'b1) $fatal(1,"Accelerator not idle before frame");
        axil_write(6'h10,input_address[31:0]); axil_write(6'h14,input_address[63:32]);
        axil_write(6'h1c,output_address[31:0]); axil_write(6'h20,output_address[63:32]);
        axil_read(6'h10,status_word); if(status_word !== input_address[31:0]) $fatal(1,"Input pointer low readback");
        axil_read(6'h14,status_word); if(status_word !== input_address[63:32]) $fatal(1,"Input pointer high readback");
        axil_read(6'h1c,status_word); if(status_word !== output_address[31:0]) $fatal(1,"Output pointer low readback");
        axil_read(6'h20,status_word); if(status_word !== output_address[63:32]) $fatal(1,"Output pointer high readback");
        rd_before=input_ram.read_beats; wr_before=output_ram.write_beats;
        case_start=cycle;
        $display("FRAME_START id=%s stalls=%0d cycle=%0d",case_id,stress,cycle);
        axil_write(0,1);
        status_word=0;
        while(!status_word[1]) begin
            repeat(4096) @(negedge ap_clk);
            axil_read(0,status_word);
            if(cycle-case_start>20000000) $fatal(1,"Frame timed out before ap_done");
        end
        repeat(20) @(negedge ap_clk);
        if(output_ram.wr_active || output_ram.bpending || output_ram.bvalid)
            $fatal(1,"Completion before write responses drained");
        mismatches=0;
        output_file={case_id,"_actual.hex"}; fd=$fopen(output_file,"w");
        if(!fd) $fatal(1,"Could not open output evidence file");
        for(i=0;i<65536;i=i+1) begin
            actual={output_ram.mem[offset_out+2*i+1],output_ram.mem[offset_out+2*i]};
            $fdisplay(fd,"%04h",actual);
            if(actual !== expected[i] || output_ram.written[offset_out+2*i] !== 1'b1 || output_ram.written[offset_out+2*i+1] !== 1'b1) begin
                if(mismatches<8) $display("MISMATCH id=%s pixel=%0d expected=%h actual=%h",case_id,i,expected[i],actual);
                mismatches=mismatches+1;
            end
        end
        $fclose(fd);
        for(i=0;i<OUT_MEM;i=i+1)
            if((i<offset_out || i>=offset_out+131072) && (output_ram.mem[i] !== 8'ha5 || output_ram.written[i] !== 0))
                $fatal(1,"Output guard corruption at %0d",i);
        if(input_ram.read_beats==rd_before || output_ram.write_beats==wr_before)
            $fatal(1,"No external memory transactions");
        if(mismatches) $fatal(1,"RTL_GOLDEN_FAIL id=%s mismatches=%0d",case_id,mismatches);
        $display("RTL_GOLDEN_PASS id=%s pixels=65536 mismatches=0 observed_cycles=%0d read_beats=%0d write_beats=%0d stalls=%0d",case_id,cycle-case_start,input_ram.read_beats-rd_before,output_ram.write_beats-wr_before,stress);
    end
    if(stress && input_ram.stalled_cycles+output_ram.stalled_cycles==0)
        $fatal(1,"Stressed run did not exercise backpressure");
    $display("RTL_SUITE_PASS frames=%0d stalls=%0d stalled_cycles=%0d",nframes,stress,input_ram.stalled_cycles+output_ram.stalled_cycles);
    $finish;
end

axi_ram #(.BASE_ADDR(IN_BASE),.MEM_BYTES(IN_MEM),.READ_ONLY(1),.WRITE_ONLY(0)) input_ram(
    .aclk(ap_clk),.aresetn(ap_rst_n),.stall_enable(stall_enable),
    .awvalid(m_axi_gmem0_AWVALID),
    .awready(m_axi_gmem0_AWREADY),
    .awaddr(m_axi_gmem0_AWADDR),
    .awid(m_axi_gmem0_AWID),
    .awlen(m_axi_gmem0_AWLEN),
    .awsize(m_axi_gmem0_AWSIZE),
    .awburst(m_axi_gmem0_AWBURST),
    .wvalid(m_axi_gmem0_WVALID),
    .wready(m_axi_gmem0_WREADY),
    .wdata(m_axi_gmem0_WDATA),
    .wstrb(m_axi_gmem0_WSTRB),
    .wlast(m_axi_gmem0_WLAST),
    .bvalid(m_axi_gmem0_BVALID),
    .bready(m_axi_gmem0_BREADY),
    .bresp(m_axi_gmem0_BRESP),
    .bid(m_axi_gmem0_BID),
    .arvalid(m_axi_gmem0_ARVALID),
    .arready(m_axi_gmem0_ARREADY),
    .araddr(m_axi_gmem0_ARADDR),
    .arid(m_axi_gmem0_ARID),
    .arlen(m_axi_gmem0_ARLEN),
    .arsize(m_axi_gmem0_ARSIZE),
    .arburst(m_axi_gmem0_ARBURST),
    .rvalid(m_axi_gmem0_RVALID),
    .rready(m_axi_gmem0_RREADY),
    .rdata(m_axi_gmem0_RDATA),
    .rlast(m_axi_gmem0_RLAST),
    .rresp(m_axi_gmem0_RRESP),
    .rid(m_axi_gmem0_RID)
);
assign m_axi_gmem0_RUSER=0;
assign m_axi_gmem0_BUSER=0;
axi_ram #(.BASE_ADDR(OUT_BASE),.MEM_BYTES(OUT_MEM),.READ_ONLY(0),.WRITE_ONLY(1)) output_ram(
    .aclk(ap_clk),.aresetn(ap_rst_n),.stall_enable(stall_enable),
    .awvalid(m_axi_gmem1_AWVALID),
    .awready(m_axi_gmem1_AWREADY),
    .awaddr(m_axi_gmem1_AWADDR),
    .awid(m_axi_gmem1_AWID),
    .awlen(m_axi_gmem1_AWLEN),
    .awsize(m_axi_gmem1_AWSIZE),
    .awburst(m_axi_gmem1_AWBURST),
    .wvalid(m_axi_gmem1_WVALID),
    .wready(m_axi_gmem1_WREADY),
    .wdata(m_axi_gmem1_WDATA),
    .wstrb(m_axi_gmem1_WSTRB),
    .wlast(m_axi_gmem1_WLAST),
    .bvalid(m_axi_gmem1_BVALID),
    .bready(m_axi_gmem1_BREADY),
    .bresp(m_axi_gmem1_BRESP),
    .bid(m_axi_gmem1_BID),
    .arvalid(m_axi_gmem1_ARVALID),
    .arready(m_axi_gmem1_ARREADY),
    .araddr(m_axi_gmem1_ARADDR),
    .arid(m_axi_gmem1_ARID),
    .arlen(m_axi_gmem1_ARLEN),
    .arsize(m_axi_gmem1_ARSIZE),
    .arburst(m_axi_gmem1_ARBURST),
    .rvalid(m_axi_gmem1_RVALID),
    .rready(m_axi_gmem1_RREADY),
    .rdata(m_axi_gmem1_RDATA),
    .rlast(m_axi_gmem1_RLAST),
    .rresp(m_axi_gmem1_RRESP),
    .rid(m_axi_gmem1_RID)
);
assign m_axi_gmem1_RUSER=0;
assign m_axi_gmem1_BUSER=0;
endmodule
