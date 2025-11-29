import asyncio
import os
import subprocess
import sys

realtime = []

def convert_model(model_path, chip='rk3588'):
    global realtime

    cwd = os.path.dirname(model_path)
    model_file = os.path.basename(model_path)

    cmd = [os.path.dirname(sys.executable) + "/yolo", 'export', f'model={model_file}', 'format=rknn', f'name={chip}']

    # Run CLI and capture stdout line by line
    with subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as process:
        for line in process.stdout: # type: ignore
            realtime.append(line)
            print(line, end='') 

        process.wait()

def reset_realtime():
    global realtime
    realtime = []
        
async def async_convert_model(model_path, chip='rk3588s'):
    await asyncio.to_thread(
        convert_model,
        model_path,
        chip,
      )

if __name__ == "__main__":
    convert_model("./uploads/best.pt")
