`timescale 1ns/1ps
// Static AXI4 memory model: one in-flight read and write, legal backpressure.
// This model intentionally supports only aligned, 32-bit INCR bursts used by
// the exported accelerator. Unsupported traffic fails rather than being guessed.
module axi_ram #(
    parameter [63:0] BASE_ADDR=0,
    parameter integer MEM_BYTES=16384,
    parameter integer READ_ONLY=0,
    parameter integer WRITE_ONLY=0
)(
    input wire aclk, aresetn, stall_enable,
    input wire awvalid, output wire awready,
    input wire [63:0] awaddr, input wire awid,
    input wire [7:0] awlen, input wire [2:0] awsize,
    input wire [1:0] awburst,
    input wire wvalid, output wire wready,
    input wire [31:0] wdata, input wire [3:0] wstrb, input wire wlast,
    output reg bvalid=0, input wire bready,
    output wire [1:0] bresp, output reg bid=0,
    input wire arvalid, output wire arready,
    input wire [63:0] araddr, input wire arid,
    input wire [7:0] arlen, input wire [2:0] arsize,
    input wire [1:0] arburst,
    output reg rvalid=0, input wire rready,
    output reg [31:0] rdata=0, output reg rlast=0,
    output wire [1:0] rresp, output reg rid=0
);
reg [7:0] mem[0:MEM_BYTES-1];
reg written[0:MEM_BYTES-1];
integer read_beats=0, write_beats=0, read_bursts=0, write_bursts=0;
integer stalled_cycles=0;
reg [63:0] active_min=BASE_ADDR, active_max=BASE_ADDR+MEM_BYTES;
integer tick=0, rd_left=0, wr_left=0, bdelay=0;
integer lane, index;
reg rd_active=0, wr_active=0, bpending=0;
reg [63:0] rd_addr=0, wr_addr=0;
reg rd_id=0;
reg aw_stalled=0, ar_stalled=0, w_stalled=0;
reg [77:0] aw_saved, ar_saved;
reg [36:0] w_saved;
wire [77:0] aw_payload={awaddr,awid,awlen,awsize,awburst};
wire [77:0] ar_payload={araddr,arid,arlen,arsize,arburst};
wire [36:0] w_payload={wdata,wstrb,wlast};
assign awready=aresetn && !wr_active && !bpending && !bvalid && (!stall_enable || tick%7!=0);
assign arready=aresetn && !rd_active && !rvalid && (!stall_enable || tick%5!=0);
assign wready=aresetn && wr_active && (!stall_enable || tick%4!=0);
assign rresp=2'b00;
assign bresp=2'b00;

task check_address(input [63:0] addr, input [7:0] len,
                   input [2:0] size, input [1:0] burst);
begin
    if(size !== 3'd2 || burst !== 2'b01 || addr[1:0] !== 2'b00)
        $fatal(1,"AXI unsupported/unknown transaction addr=%h size=%h burst=%h",addr,size,burst);
    if((^addr === 1'bx) || addr<active_min || addr+4*(len+1)>active_max)
        $fatal(1,"AXI address outside active image addr=%h len=%d min=%h max=%h",addr,len,active_min,active_max);
    if({1'b0,addr[11:0]}+4*(len+1)>4096)
        $fatal(1,"AXI burst crosses 4KiB boundary");
end
endtask

always @(posedge aclk) begin
    if(!aresetn) begin
        tick<=0; rd_active<=0; wr_active<=0; bpending<=0;
        rvalid<=0; bvalid<=0; rlast<=0;
        read_beats<=0; write_beats<=0; read_bursts<=0; write_bursts<=0;
        stalled_cycles<=0; aw_stalled<=0; ar_stalled<=0; w_stalled<=0;
    end else begin
        tick<=tick+1;
        if(aw_stalled && (awvalid !== 1'b1 || aw_payload !== aw_saved))
            $fatal(1,"AXI AW payload changed under backpressure");
        if(ar_stalled && (arvalid !== 1'b1 || ar_payload !== ar_saved))
            $fatal(1,"AXI AR payload changed under backpressure");
        if(w_stalled && (wvalid !== 1'b1 || w_payload !== w_saved))
            $fatal(1,"AXI W payload changed under backpressure");
        aw_stalled<=awvalid && !awready; aw_saved<=aw_payload;
        ar_stalled<=arvalid && !arready; ar_saved<=ar_payload;
        w_stalled<=wvalid && !wready; w_saved<=w_payload;
        if((arvalid&&!arready)||(awvalid&&!awready)||(wvalid&&!wready))
            stalled_cycles<=stalled_cycles+1;

        if(rvalid && rready) begin rvalid<=0; read_beats<=read_beats+1; end
        if(bvalid && bready) bvalid<=0;
        if(arvalid && arready) begin
            if(WRITE_ONLY) $fatal(1,"Unexpected read from output memory");
            check_address(araddr,arlen,arsize,arburst);
            rd_active<=1; rd_addr<=araddr; rd_left<=arlen+1; rd_id<=arid;
            read_bursts<=read_bursts+1;
        end
        if(rd_active && (!rvalid || rready)) begin
            rvalid<=0;
            if(!stall_enable || tick%3!=0) begin
                index=rd_addr-BASE_ADDR;
                rdata<={mem[index+3],mem[index+2],mem[index+1],mem[index]};
                rid<=rd_id; rlast<=(rd_left==1); rvalid<=1;
                if(rd_left==1) rd_active<=0;
                else begin rd_addr<=rd_addr+4; rd_left<=rd_left-1; end
            end
        end
        if(awvalid && awready) begin
            if(READ_ONLY) $fatal(1,"Unexpected write to input memory");
            check_address(awaddr,awlen,awsize,awburst);
            wr_active<=1; wr_addr<=awaddr; wr_left<=awlen+1; bid<=awid;
            write_bursts<=write_bursts+1;
        end
        if(wvalid && wready) begin
            if(wlast !== (wr_left==1)) $fatal(1,"AXI WLAST disagrees with AWLEN");
            if((^wstrb === 1'bx) || (^wdata === 1'bx)) $fatal(1,"Unknown AXI write data/strobes");
            index=wr_addr-BASE_ADDR;
            for(lane=0;lane<4;lane=lane+1) if(wstrb[lane]) begin
                mem[index+lane]<=wdata[8*lane+:8]; written[index+lane]<=1;
            end
            write_beats<=write_beats+1;
            if(wr_left==1) begin
                wr_active<=0; bpending<=1; bdelay<=stall_enable ? 3 : 0;
            end else begin wr_addr<=wr_addr+4; wr_left<=wr_left-1; end
        end
        if(bpending) begin
            if(bdelay==0) begin bvalid<=1; bpending<=0; end
            else bdelay<=bdelay-1;
        end
    end
end
endmodule
