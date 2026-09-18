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
