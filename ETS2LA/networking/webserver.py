from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import ETS2LA.backend.backend as backend
import ETS2LA.backend.settings as settings
import threading
import multiprocessing
import logging
import sys
import os
import json
from typing import Any
from fastapi import Body
import ETS2LA.variables as variables
import ETS2LA.backend.controls as controls

mainThreadQueue = []
sessionToken = ""

app = FastAPI(
    title="ETS2LA",
    description="Backend API for the ETS2 Lane Assist app",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def read_root():
    return {"ETS2LA": "1.0.0"}

@app.get("/api/frametimes")
def get_frametimes():
    return backend.frameTimes

@app.get("/api/quit")
def quitApp():
    variables.CLOSE = True
    return {"status": "ok"}

@app.get("/api/restart")
def restartApp():
    variables.RESTART = True
    return {"status": "ok"}

@app.get("/api/plugins")
def get_plugins():
    # Get data
    plugins = backend.GetAvailablePlugins()
    try:
        enabledPlugins = backend.GetEnabledPlugins()
    except:
        import traceback
        traceback.print_exc()
        enabledPlugins = []
        
    try:
        frametimes = backend.frameTimes
    except:
        import traceback
        traceback.print_exc()
        frametimes = {}
        
    # Create the json
    returnData = plugins.copy()
    for plugin in plugins:
        returnData[plugin]["enabled"] = False
        if plugin in enabledPlugins:
            returnData[plugin]["enabled"] = True
        
        returnData[plugin]["frametimes"] = 0
        if plugin in frametimes:
            returnData[plugin]["frametimes"] = frametimes[plugin]
    
    return returnData

@app.get("/api/plugins/{plugin}/enable")
def enable_plugin(plugin: str):
    return backend.AddPluginRunner(plugin)

@app.get("/api/plugins/{plugin}/disable")
def disable_plugin(plugin: str):
    return backend.RemovePluginRunner(plugin)

@app.post("/api/plugins/{plugin}/settings/{key}/set")
def set_plugin_setting(plugin: str, key: str, value: Any = Body(...)):
    success = settings.Set(plugin, key, value["value"])
    return success

@app.post("/api/plugins/{plugin}/settings/set")
def set_plugin_settings(plugin: str, data: dict = Body(...)):
    keys = data["keys"]
    setting = data["setting"]
    success = settings.Set(plugin, keys, setting)
    return success
    

@app.get("/api/plugins/{plugin}/settings/{key}")
def get_plugin_setting(plugin: str, key: str):
    return settings.Get(plugin, key)

@app.get("/api/plugins/{plugin}/settings")
def get_plugin_settings(plugin: str):
    print(plugin)
    return settings.GetJSON(plugin)

@app.post("/api/controls/{control}/change")
def change_control(control: str):
    mainThreadQueue.append([controls.ChangeKeybind, [control], {}])
    while [controls.ChangeKeybind, [control], {}] in mainThreadQueue:
        pass
    return {"status": "ok"}

@app.get("/api/git/history")
def get_git_history():
    return backend.GetGitHistory()

from pydantic import BaseModel
class PluginCallData(BaseModel):
    args: list
    kwargs: dict

@app.post("/api/plugins/{plugin}/call/{function}")
def call_plugin_function(plugin: str, function: str, data: PluginCallData = None):
    if data is None:
        data = PluginCallData()
    
    returnData = backend.CallPluginFunction(plugin, function, data.args, data.kwargs)
    if returnData == False or returnData == None:
        # Return error 500 if the plugin function failed
        raise Exception("Plugin function failed")
    else:
        return returnData


@app.get("/api/server/ip")
def get_IP():
    return IP

def RunFrontend():
    os.system("cd frontend && npm run dev")
    
def run():
    global IP
    import uvicorn
    # Get current PC ip
    import socket
    IP = socket.gethostbyname(socket.gethostname())
    hostname = "0.0.0.0"
    # Start the webserver on the local IP
    threading.Thread(target=uvicorn.run, args=(app,), kwargs={"port": 37520, "host": hostname, "log_level": "critical"}, daemon=True).start()
    logging.info(f"Webserver started on http://{IP}:37520 (& localhost:37520)")
    # Start the frontend
    p = multiprocessing.Process(target=RunFrontend, daemon=True)
    p.start()
    logging.info("Frontend started on http://localhost:3000")