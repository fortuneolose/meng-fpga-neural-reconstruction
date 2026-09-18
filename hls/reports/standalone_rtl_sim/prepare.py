"""Snapshot the preserved IP and build a standalone, class-free RTL regression."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, struct, subprocess

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    a=p.parse_args()
    root=a.repo.resolve(); run=a.run_dir.resolve(); here=Path(__file__).resolve().parent
    run.mkdir(parents=True,exist_ok=True)
    rtl=root/'vivado/ip_repo/reconstruction_accel_1_0/hdl/verilog'
    syn=root/'hls/work/hls/syn/verilog'
    files=sorted(list(rtl.glob('*.v'))+list(rtl.glob('*.dat')))
    if not files: raise RuntimeError('No packaged RTL found')
    manifest={'repository':str(root),'rtl_origin':str(rtl),'files':{},'golden_files':{},'sources':{}}
    cmd=['git','-c',f'safe.directory={root.as_posix()}','-C',str(root)]
    manifest['repository_commit']=subprocess.check_output(cmd+['rev-parse','HEAD'],text=True).strip()
    for f in files:
        shutil.copy2(f,run/f.name)
        other=syn/f.name
        manifest['files'][f.name]={'sha256':sha(f),'matches_hls_synthesis':other.exists() and sha(f)==sha(other)}
    for f in sorted((root/'hls/src').glob('*')):
        if f.is_file(): manifest['sources'][f.name]=sha(f)
    for cid in ('0805','0809','0824'):
        data=root/'hls/tb/data'/cid
        ip=data/'input_lr_u8.bin'; op=data/'output_ticks_u16.bin'
        if ip.stat().st_size!=16384 or op.stat().st_size!=131072: raise RuntimeError('Golden length mismatch')
        (run/f'{cid}_input.hex').write_text(''.join(f'{v:02x}\n' for v in ip.read_bytes()))
        (run/f'{cid}_expected.hex').write_text(''.join(f'{v[0]:04x}\n' for v in struct.iter_unpack('<H',op.read_bytes())))
        manifest['golden_files'][cid]={'input_sha256':sha(ip),'output_sha256':sha(op)}
    top=(rtl/'reconstruction_accel.v').read_text()
    params='\n'.join(re.findall(r'^parameter\s+[^;]+;',top,re.M))
    ports=re.findall(r'^(input|output)\s+(\[[^\]]+\])?\s*(\w+)\s*;',top,re.M)
    if len(ports)!=111: print(f'Discovered {len(ports)} top-level ports')
    declarations=[]
    for direction,width,name in ports:
        driven=direction=='input' and not name.startswith('m_axi_')
        declarations.append(f'{"reg" if driven else "wire"} {width or ""} {name};')
    connections=',\n'.join(f'    .{name}({name})' for _,_,name in ports)
    tb='`timescale 1ns/1ps\nmodule tb;\n'+params+'\n'+'\n'.join(declarations)+'\n'
    tb+='reconstruction_accel dut (\n'+connections+'\n);\n'
    tb+=(here/'tb_body.sv').read_text()+'\n'
    fields=['awvalid','awready','awaddr','awid','awlen','awsize','awburst',
            'wvalid','wready','wdata','wstrb','wlast','bvalid','bready','bresp','bid',
            'arvalid','arready','araddr','arid','arlen','arsize','arburst',
            'rvalid','rready','rdata','rlast','rresp','rid']
    for k,ram,base,size in [(0,'input_ram','IN_BASE','IN_MEM'),(1,'output_ram','OUT_BASE','OUT_MEM')]:
        tb+=f'axi_ram #(.BASE_ADDR({base}),.MEM_BYTES({size}),.READ_ONLY({1-k}),.WRITE_ONLY({k})) {ram}(\n'
        tb+='    .aclk(ap_clk),.aresetn(ap_rst_n),.stall_enable(stall_enable),\n'
        tb+=',\n'.join(f'    .{field}(m_axi_gmem{k}_{field.upper()})' for field in fields)+'\n);\n'
        tb+=f'assign m_axi_gmem{k}_RUSER=0;\nassign m_axi_gmem{k}_BUSER=0;\n'
    tb+='endmodule\n'
    (run/'tb.sv').write_text(tb)
    shutil.copy2(here/'axi_ram.sv',run/'axi_ram.sv')
    (run/'rtl.prj').write_text(''.join(f'verilog work "{f.name}"\n' for f in files if f.suffix=='.v')+'sv work "axi_ram.sv"\nsv work "tb.sv"\n')
    (run/'iverilog.f').write_text('\n'.join(f.name for f in files if f.suffix=='.v')+'\naxi_ram.sv\ntb.sv\n')
    (run/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(f'Snapshot: {len(files)} RTL/ROM files; {sum(v["matches_hls_synthesis"] for v in manifest["files"].values())} byte-identical to synthesis directory')
    print(f'Prepared: {run}')

if __name__=='__main__': main()
